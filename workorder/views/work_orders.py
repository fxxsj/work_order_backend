"""
WorkOrder 视图集
"""

"""
核心业务视图集

包含施工单、工序、任务、产品、物料、日志等核心业务视图集。
"""

from rest_framework import viewsets, status, filters, serializers
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
    DraftTaskSerializer,
    WorkOrderTaskSerializer
)



class WorkOrderViewSet(viewsets.ModelViewSet):
    """施工单视图集"""
    queryset = WorkOrder.objects.all()
    permission_classes = [WorkOrderDataPermission]  # 使用细粒度数据权限
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'customer', 'manager', 'approval_status']
    search_fields = ['order_number', 'products__product__name', 'products__product__code', 'customer__name']
    ordering_fields = ['created_at', 'order_date', 'delivery_date', 'order_number']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return WorkOrderListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return WorkOrderCreateUpdateSerializer
        return WorkOrderDetailSerializer
    
    def update(self, request, *args, **kwargs):
        """重写update方法以捕获详细错误信息（P1 优化：使用日志记录）"""
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            import traceback
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in WorkOrderViewSet.update: {str(e)}", exc_info=True)
            raise
    
    def get_queryset(self):
        """根据用户权限过滤查询集，使用查询优化器提升性能"""
        from ..services.query_optimizer import QueryOptimizer, QueryCache
        
        # 使用查询优化器获取基础查询集
        queryset = QueryOptimizer.optimize_workorder_queryset(
            super().get_queryset(), 
            include_details=False  # 列表视图不需要详细信息
        )
        
        user = self.request.user
        cache_key = f'workorder_queryset_{user.id}_{user.is_superuser}'

        # 管理员可以查看所有数据
        if user.is_superuser:
            return queryset

        # 使用缓存优化权限查询
        def get_filtered_queryset():
            if user.groups.filter(name='业务员').exists():
                return queryset.filter(customer__salesperson=user)
            
            elif user.has_perm('workorder.change_workorder'):
                user_departments = user.profile.departments.all() if hasattr(user, 'profile') else []
                if user_departments:
                    # 使用优化的子查询，添加 select_related 优化跨表查询性能
                    from ..models.core import WorkOrderTask
                    work_order_ids = WorkOrderTask.objects.filter(
                        assigned_department__in=user_departments
                    ).select_related(
                        'work_order_process'  # 优化跨表查询，避免N+1问题
                    ).values_list(
                        'work_order_process__work_order_id', flat=True
                    ).distinct()
                    return queryset.filter(id__in=work_order_ids)
                else:
                    return queryset.filter(created_by=user)
            
            else:
                return queryset.filter(created_by=user)
        
        return QueryCache.get_cached_queryset(cache_key, get_filtered_queryset, timeout=300)
    
    def perform_create(self, serializer):
        # 自动设置创建人和制表人为当前用户
        serializer.save(
            created_by=self.request.user,
            manager=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def add_process(self, request, pk=None):
        """为施工单添加工序"""
        work_order = self.get_object()
        process_id = request.data.get('process_id')
        sequence = request.data.get('sequence', 0)
        
        if not process_id:
            return Response(
                {'error': '请提供工序ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            process = Process.objects.get(id=process_id)
        except Process.DoesNotExist:
            return Response(
                {'error': '工序不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 检查是否已存在相同 sequence 的工序
        # 如果存在，自动调整 sequence 为下一个可用的值
        existing_process = WorkOrderProcess.objects.filter(
            work_order=work_order,
            sequence=sequence
        ).first()
        
        if existing_process:
            # 找到该施工单中最大的 sequence，然后加1
            max_sequence = WorkOrderProcess.objects.filter(
                work_order=work_order
            ).aggregate(Max('sequence'))['sequence__max'] or 0
            sequence = max_sequence + 1
        
        # 检查是否已经存在相同的工序（同一个施工单和同一个工序）
        existing_same_process = WorkOrderProcess.objects.filter(
            work_order=work_order,
            process=process
        ).first()
        
        if existing_same_process:
            return Response(
                {'error': '该工序已经添加到施工单中'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        work_order_process = WorkOrderProcess.objects.create(
            work_order=work_order,
            process=process,
            sequence=sequence
        )
        
        serializer = WorkOrderProcessSerializer(work_order_process)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def add_material(self, request, pk=None):
        """为施工单添加物料"""
        work_order = self.get_object()
        material_id = request.data.get('material_id')
        notes = request.data.get('notes', '')
        
        if not material_id:
            return Response(
                {'error': '请提供物料ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            material = Material.objects.get(id=material_id)
        except Material.DoesNotExist:
            return Response(
                {'error': '物料不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        work_order_material = WorkOrderMaterial.objects.create(
            work_order=work_order,
            material=material,
            notes=notes
        )
        
        serializer = WorkOrderMaterialSerializer(work_order_material)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """更新施工单状态"""
        work_order = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(WorkOrder.STATUS_CHOICES):
            return Response(
                {'error': '无效的状态'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        work_order.status = new_status
        work_order.save()
        
        serializer = self.get_serializer(work_order)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], throttle_classes=[ApprovalRateThrottle])
    def approve(self, request, pk=None):
        """业务员审核施工单（完善版 - P1 优化：添加速率限制和输入验证）"""
        from ..models.system import WorkOrderApprovalLog, Notification

        work_order = self.get_object()

        # P1 优化: 输入验证
        approval_status = request.data.get('approval_status')
        if approval_status not in ['approved', 'rejected']:
            return Response(
                {'error': '审核状态无效，必须是 approved 或 rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 检查用户是否为业务员
        if not request.user.groups.filter(name='业务员').exists():
            return Response(
                {'error': '只有业务员可以审核施工单'},
                status=status.HTTP_403_FORBIDDEN
            )

        # 检查业务员是否负责该施工单的客户
        if work_order.customer.salesperson != request.user:
            return Response(
                {'error': '只能审核自己负责的施工单'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 检查当前审核状态（只有待审核的施工单才能审核）
        # 注意：通过 request_reapproval 接口请求重新审核后，状态会重置为 pending
        if work_order.approval_status != 'pending':
            return Response(
                {'error': '只有待审核的施工单可以审核。如需重新审核，请先使用"请求重新审核"功能。'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        approval_status = request.data.get('approval_status')  # 'approved' 或 'rejected'
        approval_comment = request.data.get('approval_comment', '')
        rejection_reason = request.data.get('rejection_reason', '')
        
        if approval_status not in ['approved', 'rejected']:
            return Response(
                {'error': '审核状态必须是 approved 或 rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 审核拒绝时，强制要求填写拒绝原因
        if approval_status == 'rejected' and not rejection_reason:
            return Response(
                {'error': '审核拒绝时，必须填写拒绝原因'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 审核前数据完整性检查
        validation_errors = work_order.validate_before_approval()
        if validation_errors:
            return Response(
                {'error': '施工单数据不完整，无法审核', 'details': validation_errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 记录审核历史
        approval_log = WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            approval_status=approval_status,
            approved_by=request.user,
            approval_comment=approval_comment,
            rejection_reason=rejection_reason
        )
        
        # 更新审核信息
        work_order.approval_status = approval_status
        work_order.approved_by = request.user
        work_order.approved_at = timezone.now()
        work_order.approval_comment = approval_comment
        
        # 审核通过后，自动变更施工单状态
        if approval_status == 'approved' and work_order.status == 'pending':
            work_order.status = 'in_progress'
        
        work_order.save()
        
        # 创建通知
        if approval_status == 'approved':
            Notification.create_notification(
                recipient=work_order.created_by,
                notification_type='approval_passed',
                title=f'施工单 {work_order.order_number} 审核通过',
                content=f'施工单 {work_order.order_number} 已通过审核，状态已变更为"进行中"。' + (f'审核意见：{approval_comment}' if approval_comment else ''),
                priority='high',
                work_order=work_order
            )
        else:
            Notification.create_notification(
                recipient=work_order.created_by,
                notification_type='approval_rejected',
                title=f'施工单 {work_order.order_number} 审核拒绝',
                content=f'施工单 {work_order.order_number} 审核被拒绝。拒绝原因：{rejection_reason}',
                priority='high',
                work_order=work_order
            )
        
        serializer = self.get_serializer(work_order)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def resubmit_for_approval(self, request, pk=None):
        """重新提交审核（审核拒绝后使用）"""
        work_order = self.get_object()
        
        # 检查当前审核状态（只有被拒绝的施工单才能重新提交）
        if work_order.approval_status != 'rejected':
            return Response(
                {'error': '只有被拒绝的施工单才能重新提交审核'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查用户是否有权限（制表人或创建人）
        if work_order.manager != request.user and work_order.created_by != request.user:
            # 检查是否有编辑施工单的权限
            if not request.user.has_perm('workorder.change_workorder'):
                return Response(
                    {'error': '只有制表人、创建人或有编辑权限的用户才能重新提交审核'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # 重置审核状态为 pending
        work_order.approval_status = 'pending'
        # 清空之前的审核信息，允许重新审核
        work_order.approval_comment = ''
        work_order.save()
        
        serializer = self.get_serializer(work_order)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def request_reapproval(self, request, pk=None):
        """请求重新审核（审核通过后发现错误需要修改）
        
        使用场景：
        - 审核通过后发现需要修改核心字段（产品、工序、版等）
        - 审核通过后发现需要添加工序
        - 审核通过后发现数据错误需要修正
        
        流程：
        1. 检查权限（只有创建人或制表人可以请求重新审核）
        2. 检查状态（只有已审核通过的施工单可以请求重新审核）
        3. 重置审核状态为 pending
        4. 重置施工单状态为 pending（如果已开始，需要重置）
        5. 通知原审核人
        """
        from ..models.system import Notification
        
        work_order = self.get_object()
        
        # 检查权限：只有创建人或制表人可以请求重新审核
        if work_order.created_by != request.user and work_order.manager != request.user:
            # 检查是否有编辑施工单的权限
            if not request.user.has_perm('workorder.change_workorder'):
                return Response(
                    {'error': '只有创建人、制表人或有编辑权限的用户可以请求重新审核'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # 检查状态：只有已审核通过的施工单可以请求重新审核
        if work_order.approval_status != 'approved':
            return Response(
                {'error': '只有已审核通过的施工单可以请求重新审核'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取请求原因（可选，但建议填写）
        request_reason = request.data.get('reason', '')
        
        # 记录原审核人
        original_approver = work_order.approved_by
        
        # 重置审核状态
        work_order.approval_status = 'pending'
        # 如果施工单已开始，重置状态为 pending（需要重新审核后才能开始）
        if work_order.status == 'in_progress':
            work_order.status = 'pending'
        # 保留原审核人信息（用于通知），但清空审核意见
        # work_order.approved_by 保持不变，用于通知原审核人
        work_order.approval_comment = ''
        work_order.save()
        
        # 创建通知（通知原审核人）
        if original_approver:
            notification_content = f'施工单 {work_order.order_number} 已修改，请求重新审核。'
            if request_reason:
                notification_content += f' 请求原因：{request_reason}'
            
            Notification.create_notification(
                recipient=original_approver,
                notification_type='reapproval_requested',
                title=f'施工单 {work_order.order_number} 请求重新审核',
                content=notification_content,
                priority='high',
                work_order=work_order
            )
        
        # 创建通知（通知创建人，确认已提交重新审核请求）
        if work_order.created_by and work_order.created_by != request.user:
            Notification.create_notification(
                recipient=work_order.created_by,
                notification_type='reapproval_requested',
                title=f'施工单 {work_order.order_number} 已提交重新审核请求',
                content=f'施工单 {work_order.order_number} 已提交重新审核请求，等待业务员审核。',
                priority='normal',
                work_order=work_order
            )
        
        serializer = self.get_serializer(work_order)
        return Response({
            **serializer.data,
            'message': '重新审核请求已提交，已通知原审核人',
            'original_approver': original_approver.username if original_approver else None
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """统计数据（增强版：包含任务统计和生产效率分析）"""
        from datetime import timedelta
        
        queryset = self.filter_queryset(self.get_queryset())
        
        total_count = queryset.count()
        
        # 状态统计：确保所有状态都有数据，即使数量为0
        status_stats = list(queryset.values('status').annotate(count=Count('id')).order_by('status'))
        # 确保所有状态都包含在内
        all_statuses = ['pending', 'in_progress', 'paused', 'completed', 'cancelled']
        status_dict = {item['status']: item['count'] for item in status_stats}
        status_statistics = [{'status': status, 'count': status_dict.get(status, 0)} for status in all_statuses]
        
        # 优先级统计：确保所有优先级都有数据，即使数量为0
        priority_stats = list(queryset.values('priority').annotate(count=Count('id')).order_by('priority'))
        # 确保所有优先级都包含在内
        all_priorities = ['low', 'normal', 'high', 'urgent']
        priority_dict = {item['priority']: item['count'] for item in priority_stats}
        priority_statistics = [{'priority': priority, 'count': priority_dict.get(priority, 0)} for priority in all_priorities]
        
        # 即将到期的订单（7天内）
        upcoming_deadline = queryset.filter(
            delivery_date__lte=timezone.now().date() + timedelta(days=7),
            status__in=['pending', 'in_progress']
        ).count()
        
        # 未审核施工单数量（仅业务员可见，只统计自己负责的）
        pending_approval_count = 0
        if request.user.groups.filter(name='业务员').exists():
            pending_approval_count = queryset.filter(
                approval_status='pending',
                customer__salesperson=request.user
            ).count()
        
        # ========== 新增：任务统计 ==========
        from ..models.core import WorkOrderTask, WorkOrderProcess
        
        # 任务总数统计
        all_tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order__in=queryset
        )
        task_total_count = all_tasks.count()
        
        # 任务状态统计
        task_status_stats = list(all_tasks.values('status').annotate(count=Count('id')).order_by('status'))
        all_task_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
        task_status_dict = {item['status']: item['count'] for item in task_status_stats}
        task_status_statistics = [
            {'status': status, 'count': task_status_dict.get(status, 0)} 
            for status in all_task_statuses
        ]
        
        # 任务类型统计
        task_type_stats = list(all_tasks.values('task_type').annotate(count=Count('id')).order_by('task_type'))
        task_type_statistics = [
            {'task_type': item['task_type'], 'count': item['count']} 
            for item in task_type_stats
        ]
        
        # 按部门统计任务
        task_dept_stats = list(
            all_tasks.filter(assigned_department__isnull=False)
            .values('assigned_department__name')
            .annotate(count=Count('id'), completed=Count('id', filter=Q(status='completed')))
            .order_by('-count')
        )
        task_department_statistics = [
            {
                'department': item['assigned_department__name'],
                'total': item['count'],
                'completed': item['completed'],
                'completion_rate': round(item['completed'] / item['count'] * 100, 2) if item['count'] > 0 else 0
            }
            for item in task_dept_stats
        ]
        
        # ========== 新增：生产效率分析 ==========
        
        # 工序完成率统计
        all_processes = WorkOrderProcess.objects.filter(work_order__in=queryset)
        process_total = all_processes.count()
        process_completed = all_processes.filter(status='completed').count()
        process_completion_rate = round(process_completed / process_total * 100, 2) if process_total > 0 else 0
        
        # 平均完成时间（已完成工序）
        completed_processes = all_processes.filter(
            status='completed',
            actual_start_time__isnull=False,
            actual_end_time__isnull=False
        )
        avg_completion_time = None
        if completed_processes.exists():
            # 计算平均完成时间（小时）
            completion_times = []
            for process in completed_processes:
                if process.actual_start_time and process.actual_end_time:
                    delta = process.actual_end_time - process.actual_start_time
                    completion_times.append(delta.total_seconds() / 3600)  # 转换为小时
            
            if completion_times:
                avg_completion_time = round(sum(completion_times) / len(completion_times), 2)
        
        # 任务完成率统计
        task_completed = all_tasks.filter(status='completed').count()
        task_completion_rate = round(task_completed / task_total_count * 100, 2) if task_total_count > 0 else 0
        
        # 不良品率统计（已完成任务）
        completed_tasks = all_tasks.filter(status='completed')
        total_production_quantity = completed_tasks.aggregate(
            total=Sum('production_quantity', default=0)
        )['total']
        total_defective_quantity = completed_tasks.aggregate(
            total=Sum('quantity_defective', default=0)
        )['total']
        defective_rate = round(total_defective_quantity / total_production_quantity * 100, 2) if total_production_quantity > 0 else 0
        
        # 按客户统计
        customer_stats = list(
            queryset.values('customer__name')
            .annotate(
                count=Count('id'),
                completed=Count('id', filter=Q(status='completed'))
            )
            .order_by('-count')[:10]  # 前10个客户
        )
        customer_statistics = [
            {
                'customer': item['customer__name'],
                'total': item['count'],
                'completed': item['completed'],
                'completion_rate': round(item['completed'] / item['count'] * 100, 2) if item['count'] > 0 else 0
            }
            for item in customer_stats
        ]
        
        # 按产品统计
        from ..models.core import WorkOrderProduct
        product_stats = list(
            WorkOrderProduct.objects.filter(work_order__in=queryset)
            .values('product__name', 'product__code')
            .annotate(
                count=Count('work_order', distinct=True),
                total_quantity=Sum('quantity')
            )
            .order_by('-count')[:10]  # 前10个产品
        )
        product_statistics = [
            {
                'product_name': item['product__name'],
                'product_code': item['product__code'],
                'order_count': item['count'],
                'total_quantity': item['total_quantity']
            }
            for item in product_stats
        ]
        
        return Response({
            # 基础统计
            'total_count': total_count,
            'status_statistics': status_statistics,
            'priority_statistics': priority_statistics,
            'upcoming_deadline_count': upcoming_deadline,
            'pending_approval_count': pending_approval_count,
            
            # 任务统计
            'task_statistics': {
                'total_count': task_total_count,
                'status_statistics': task_status_statistics,
                'type_statistics': task_type_statistics,
                'department_statistics': task_department_statistics,
                'completion_rate': task_completion_rate,
            },
            
            # 生产效率分析
            'efficiency_analysis': {
                'process_completion_rate': process_completion_rate,
                'process_total': process_total,
                'process_completed': process_completed,
                'avg_completion_time_hours': avg_completion_time,
                'task_completion_rate': task_completion_rate,
                'defective_rate': defective_rate,
                'total_production_quantity': total_production_quantity,
                'total_defective_quantity': total_defective_quantity,
            },
            
            # 业务分析
            'business_analysis': {
                'customer_statistics': customer_statistics,
                'product_statistics': product_statistics,
            },
        })
    
    @action(detail=False, methods=['get'], throttle_classes=[ExportRateThrottle])
    def export(self, request):
        """导出施工单列表到 Excel（P1 优化：添加速率限制）"""
        # 权限检查：需要查看权限
        if not request.user.has_perm('workorder.view_workorder'):
            return Response(
                {'error': '您没有权限导出施工单数据'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 获取过滤后的查询集（使用 get_queryset 确保权限过滤）
        queryset = self.filter_queryset(self.get_queryset())
        
        # 记录导出日志（可选）
        # 这里可以添加导出日志记录功能
        
        # 导出 Excel
        filename = request.query_params.get('filename')
        return export_work_orders(queryset, filename)


class DraftTaskViewSet(viewsets.ModelViewSet):
    """草稿任务视图集（允许编辑和删除草稿状态的任务）"""
    serializer_class = DraftTaskSerializer
    permission_classes = [WorkOrderTaskPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'task_type', 'work_order_process']
    search_fields = ['work_content', 'description']
    ordering_fields = ['created_at', 'production_quantity', 'estimated_hours']
    ordering = ['-created_at']

    def get_queryset(self):
        """只返回草稿状态的任务"""
        user = self.request.user

        # 获取草稿任务
        queryset = WorkOrderTask.objects.filter(status='draft').select_related(
            'work_order_process__work_order__customer',
            'work_order_process__process',
            'assigned_department',
            'assigned_operator'
        )

        # 权限过滤：基于施工单的数据权限
        if not user.is_superuser:
            # 管理员可以看到所有草稿任务
            if not user.has_perm('workorder.manage_all_workorders'):
                # 普通用户只能看到自己创建的施工单的草稿任务
                queryset = queryset.filter(
                    work_order_process__work_order__created_by=user
                )

        return queryset

    def perform_update(self, serializer):
        """更新前验证"""
        instance = self.get_object()

        # 确保任务仍为草稿状态
        if instance.status != 'draft':
            raise serializers.ValidationError(
                "只能编辑草稿状态的任务。当前任务状态为：{}".format(
                    instance.get_status_display()
                )
            )

        # 检查施工单是否已审核
        work_order = instance.work_order_process.work_order
        if work_order.approval_status == 'approved':
            raise serializers.ValidationError(
                "已审核的施工单不允许编辑草稿任务"
            )

        # 保存更新
        serializer.save(status='draft')

    def perform_destroy(self, instance):
        """删除前验证"""
        # 确保任务仍为草稿状态
        if instance.status != 'draft':
            raise serializers.ValidationError(
                "只能删除草稿状态的任务。当前任务状态为：{}".format(
                    instance.get_status_display()
                )
            )

        # 检查施工单是否已审核
        work_order = instance.work_order_process.work_order
        if work_order.approval_status == 'approved':
            raise serializers.ValidationError(
                "已审核的施工单不允许删除草稿任务"
            )

        # 删除任务
        instance.delete()

    @action(detail=False, methods=['patch'])
    def bulk_update(self, request):
        """批量更新草稿任务

        请求体格式：
        {
            "task_ids": [1, 2, 3],
            "updates": {
                "estimated_hours": 8,
                "description": "批量更新的描述"
            }
        }
        """
        task_ids = request.data.get('task_ids', [])
        updates = request.data.get('updates', {})

        if not task_ids:
            return Response(
                {'error': '请提供要更新的任务ID列表'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not updates:
            return Response(
                {'error': '请提供要更新的字段'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取任务并验证权限
        queryset = self.get_queryset().filter(id__in=task_ids)

        if queryset.count() != len(task_ids):
            return Response(
                {'error': '部分任务不存在或无权访问'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 批量更新
        updated_count = 0
        for task in queryset:
            # 验证任务状态
            if task.status != 'draft':
                continue

            # 验证施工单状态
            work_order = task.work_order_process.work_order
            if work_order.approval_status == 'approved':
                continue

            # 更新字段
            for field, value in updates.items():
                if hasattr(task, field):
                    setattr(task, field, value)

            task.status = 'draft'  # 确保状态保持为 draft
            task.save()
            updated_count += 1

        return Response({
            'message': f'成功更新 {updated_count} 个草稿任务',
            'updated_count': updated_count,
            'total_requested': len(task_ids)
        })

