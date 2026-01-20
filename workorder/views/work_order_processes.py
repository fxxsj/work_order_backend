"""
WorkOrderProcess 视图集
"""

"""
核心业务视图集

包含施工单、工序、任务、产品、物料、日志等核心业务视图集。
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import FilterSet, NumberFilter, CharFilter
from django.db.models import Q, Count, Sum, Max, Avg, F
from django.db import models
from django.utils import timezone
from decimal import Decimal

from ..permissions import (
    WorkOrderProcessPermission,
    WorkOrderMaterialPermission,
    WorkOrderTaskPermission,
    WorkOrderDataPermission
)
from ..export_utils import export_work_orders, export_tasks
from ..permissions import SuperuserFriendlyModelPermissions
# P1 优化: 导入自定义速率限制
from ..throttling import ApprovalRateThrottle, ExportRateThrottle, CreateRateThrottle

from ..models.base import Customer, Department, Process
from ..models.products import Product, ProductMaterial
from ..models.materials import Material
from ..models.core import (
    WorkOrder, WorkOrderProcess, WorkOrderMaterial,
    WorkOrderProduct, ProcessLog, WorkOrderTask
)
from ..models.assets import Artwork, Die

from ..serializers.base import ProcessSerializer
from ..serializers.core import (
    WorkOrderListSerializer,
    WorkOrderDetailSerializer,
    WorkOrderCreateUpdateSerializer,
    WorkOrderProcessSerializer,
    WorkOrderProcessUpdateSerializer,
    WorkOrderMaterialSerializer,
    WorkOrderProductSerializer,
    ProcessLogSerializer,
    WorkOrderTaskSerializer
)



class WorkOrderProcessViewSet(viewsets.ModelViewSet):
    """施工单工序视图集"""
    queryset = WorkOrderProcess.objects.select_related('process', 'department', 'operator', 'work_order')
    permission_classes = [WorkOrderProcessPermission]  # 使用自定义权限：如果有编辑施工单权限，就可以编辑其工序
    serializer_class = WorkOrderProcessSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['work_order', 'process', 'status', 'operator', 'department']
    search_fields = ['work_order__order_number', 'process__name', 'department__name']
    ordering_fields = ['sequence', 'actual_start_time', 'created_at']
    ordering = ['work_order', 'sequence']
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return WorkOrderProcessUpdateSerializer
        return WorkOrderProcessSerializer
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始工序（生成任务）"""
        process = self.get_object()
        
        # 检查是否可以开始
        if not process.can_start():
            return Response(
                {'error': '该工序不能开始，请先完成前置工序'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 如果状态不是 pending，不能重新开始
        if process.status != 'pending':
            return Response(
                {'error': '该工序已经开始或完成，不能重新开始'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 生成任务
        process.generate_tasks()
        
        # 更新工序状态
        process.status = 'in_progress'
        process.actual_start_time = timezone.now()
        if request.data.get('operator'):
            process.operator_id = request.data.get('operator')
        if request.data.get('department'):
            process.department_id = request.data.get('department')
        process.save()
        
        # 记录日志
        ProcessLog.objects.create(
            work_order_process=process,
            log_type='start',
            content='开始工序',
            operator=request.user
        )
        
        # 生成任务（在工序开始时自动生成）
        process.generate_tasks()
        
        serializer = self.get_serializer(process)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成工序
        
        完成逻辑：
        1. 优先检查是否所有任务已完成，如果是则自动完成（推荐方式）
        2. 如果任务未完成，需要提供强制完成原因（force_complete=True）
        3. 强制完成时会同步更新所有任务状态为已完成
        """
        process = self.get_object()
        
        # 检查状态
        if process.status != 'in_progress':
            return Response(
                {'error': '只有进行中的工序才能完成'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取完成数量和不良品数量
        quantity_completed = request.data.get('quantity_completed', 0)
        quantity_defective = request.data.get('quantity_defective', 0)
        force_complete = request.data.get('force_complete', False)
        force_reason = request.data.get('force_reason', '')
        
        # 检查任务完成情况
        tasks = process.tasks.all()
        incomplete_tasks = tasks.exclude(status='completed')
        
        # 如果任务未完成，尝试自动完成（检查是否满足自动完成条件）
        if incomplete_tasks.exists():
            # 尝试自动完成检查
            if process.check_and_update_status():
                # 自动完成成功，汇总任务的不良品数量
                # 如果手动提供了不良品数量，则使用手动值；否则使用任务汇总值
                if quantity_defective > 0:
                    process.quantity_defective = quantity_defective
                # quantity_completed 已经在 check_and_update_status 中汇总了
                # 如果手动提供了完成数量，则使用手动值（覆盖汇总值）
                if quantity_completed > 0:
                    process.quantity_completed = quantity_completed
                process.save()
                
                ProcessLog.objects.create(
                    work_order_process=process,
                    log_type='complete',
                    content=f'自动完成工序（所有任务已完成），完成数量：{process.quantity_completed}，不良品数量：{process.quantity_defective}',
                    operator=request.user
                )
                
                serializer = self.get_serializer(process)
                return Response(serializer.data)
            
            # 自动完成失败，需要强制完成
            if not force_complete:
                incomplete_count = incomplete_tasks.count()
                return Response(
                    {
                        'error': f'该工序还有 {incomplete_count} 个任务未完成，无法完成工序',
                        'incomplete_tasks': incomplete_count,
                        'requires_force': True,
                        'message': '请先完成所有任务，或提供强制完成原因进行强制完成'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 强制完成：需要提供原因
            if not force_reason:
                return Response(
                    {'error': '强制完成工序需要提供完成原因'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 强制完成：将所有未完成的任务标记为已完成
            for task in incomplete_tasks:
                task.status = 'completed'
                # 如果任务有生产数量但完成数量为0，设置为生产数量
                if task.production_quantity and not task.quantity_completed:
                    task.quantity_completed = task.production_quantity
                task.save()
                
                # 记录任务强制完成日志
                from ..models.core import TaskLog
                TaskLog.objects.create(
                    task=task,
                    log_type='status_change',
                    content=f'强制完成（因工序强制完成），原因：{force_reason}',
                    operator=request.user
                )
        
        # 更新工序信息
        process.quantity_completed = quantity_completed
        process.quantity_defective = quantity_defective
        process.status = 'completed'
        process.actual_end_time = timezone.now()
        process.save()
        
        # 记录日志
        log_content = f'完成工序，完成数量：{quantity_completed}，不良品数量：{quantity_defective}'
        if force_complete:
            log_content += f'（强制完成，原因：{force_reason}）'
        
        ProcessLog.objects.create(
            work_order_process=process,
            log_type='complete',
            content=log_content,
            operator=request.user
        )
        
        # 检查是否所有工序都完成，如果是则自动标记施工单为完成
        work_order = process.work_order
        all_processes_completed = work_order.order_processes.exclude(
            status='completed'
        ).count() == 0
        
        if all_processes_completed and work_order.status != 'completed':
            work_order.status = 'completed'
            work_order.save()
        
        serializer = self.get_serializer(process)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def batch_start(self, request):
        """批量开始工序

        请求参数：
        - process_ids: 工序ID列表（必填）
        - operator: 操作员ID（可选，应用到所有工序）
        - department: 部门ID（可选，应用到所有工序）
        """
        from ..models.core import ProcessLog
        
        process_ids = request.data.get('process_ids', [])
        operator_id = request.data.get('operator')
        department_id = request.data.get('department')
        
        if not process_ids:
            return Response(
                {'error': '请提供工序ID列表'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取工序
        processes = WorkOrderProcess.objects.filter(id__in=process_ids)
        if processes.count() != len(process_ids):
            return Response(
                {'error': '部分工序不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 批量开始工序
        started_processes = []
        failed_processes = []
        
        for process in processes:
            try:
                # 检查是否可以开始
                if not process.can_start():
                    failed_processes.append({
                        'process_id': process.id,
                        'error': '该工序不能开始，请先完成前置工序'
                    })
                    continue
                
                # 如果状态不是 pending，不能重新开始
                if process.status != 'pending':
                    failed_processes.append({
                        'process_id': process.id,
                        'error': '该工序已经开始或完成，不能重新开始'
                    })
                    continue
                
                # 生成任务
                process.generate_tasks()
                
                # 更新工序状态
                process.status = 'in_progress'
                process.actual_start_time = timezone.now()
                if operator_id:
                    process.operator_id = operator_id
                if department_id:
                    process.department_id = department_id
                process.save()
                
                # 记录日志
                ProcessLog.objects.create(
                    work_order_process=process,
                    log_type='start',
                    content='批量开始工序',
                    operator=request.user
                )
                
                started_processes.append(process.id)
                
            except Exception as e:
                failed_processes.append({
                    'process_id': process.id,
                    'error': str(e)
                })
        
        return Response({
            'message': f'成功开始 {len(started_processes)} 个工序，失败 {len(failed_processes)} 个',
            'started_count': len(started_processes),
            'failed_count': len(failed_processes),
            'started_process_ids': started_processes,
            'failed_processes': failed_processes
        })
    
    @action(detail=True, methods=['post'])
    def reassign_tasks(self, request, pk=None):
        """批量重新分派工序的所有任务到新部门/操作员
        
        使用场景：
        - 工序自动分派后，发现部门无法处理，需要整体调整为外协
        - 批量调整工序下所有任务的分派
        - 例如：裱坑工序从包装车间调整为外协车间
        
        请求参数：
        - assigned_department: 新分派部门ID（可选）
        - assigned_operator: 新分派操作员ID（可选，清空传null）
        - reason: 调整原因（必填）
        - notes: 备注（可选）
        - update_process_department: 是否同时更新工序级别的部门（默认false）
        """
        from ..models.core import TaskLog
        
        work_order_process = self.get_object()
        department_id = request.data.get('assigned_department')
        operator_id = request.data.get('assigned_operator')
        reason = request.data.get('reason', '')
        notes = request.data.get('notes', '')
        update_process_department = request.data.get('update_process_department', False)
        
        # 验证必填字段
        if not reason:
            return Response(
                {'error': '调整原因不能为空，请说明为什么需要调整分派'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取所有任务
        tasks = work_order_process.tasks.all()
        if not tasks.exists():
            return Response(
                {'error': '该工序还没有生成任务'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 验证部门
        new_department = None
        if department_id:
            try:
                from ..models.base import Department
                new_department = Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                return Response(
                    {'error': '部门不存在'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # 验证操作员
        new_operator = None
        if operator_id:
            try:
                from django.contrib.auth.models import User
                new_operator = User.objects.get(id=operator_id)
            except User.DoesNotExist:
                return Response(
                    {'error': '操作员不存在'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # 批量更新任务
        updated_count = 0
        for task in tasks:
            changed = False
            old_dept = task.assigned_department
            old_op = task.assigned_operator
            
            # 更新部门
            if department_id is not None:
                if department_id:
                    task.assigned_department = new_department
                    changed = changed or (old_dept != new_department)
                else:
                    task.assigned_department = None
                    changed = changed or (old_dept is not None)
            
            # 更新操作员
            if operator_id is not None:
                if operator_id:
                    task.assigned_operator = new_operator
                    changed = changed or (old_op != new_operator)
                else:
                    task.assigned_operator = None
                    changed = changed or (old_op is not None)
            
            if changed:
                task.save()
                updated_count += 1
                
                # 记录调整日志
                changes = []
                if department_id is not None:
                    old_dept_name = old_dept.name if old_dept else '未分配'
                    new_dept_name = new_department.name if new_department else '未分配'
                    changes.append(f"部门：{old_dept_name} → {new_dept_name}")
                if operator_id is not None:
                    old_op_name = f"{old_op.first_name}{old_op.last_name}" if old_op else '未分配'
                    new_op_name = f"{new_operator.first_name}{new_operator.last_name}" if new_operator else '未分配'
                    changes.append(f"操作员：{old_op_name} → {new_op_name}")
                
                log_content = f'批量调整任务分派：{", ".join(changes)}，原因：{reason}'
                if notes:
                    log_content += f'，备注：{notes}'
                
                TaskLog.objects.create(
                    task=task,
                    log_type='status_change',
                    content=log_content,
                    operator=request.user
                )
        
        # 如果需要，同时更新工序级别的部门
        if update_process_department and department_id:
            work_order_process.department = new_department
            work_order_process.save()
        
        serializer = self.get_serializer(work_order_process)
        return Response({
            **serializer.data,
            'message': f'成功调整 {updated_count} 个任务的分派',
            'updated_tasks_count': updated_count,
            'total_tasks_count': tasks.count()
        })
    

