from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import FilterSet, NumberFilter, CharFilter
from django.db.models import Q, Count, Sum, Max, Avg, F
from django.db import models
from django.utils import timezone
from .permissions import WorkOrderProcessPermission, WorkOrderMaterialPermission
from rest_framework.permissions import DjangoModelPermissions
from .models import (
    Customer, Department, Process, Product, ProductMaterial, Material, WorkOrder,
    WorkOrderProcess, WorkOrderMaterial, WorkOrderProduct, ProcessLog, Artwork, ArtworkProduct,
    Die, DieProduct, FoilingPlate, FoilingPlateProduct, EmbossingPlate, EmbossingPlateProduct,
    WorkOrderTask, ProductGroup, ProductGroupItem, WorkOrderApprovalLog, TaskAssignmentRule, Notification
)
from .serializers import (
    CustomerSerializer, DepartmentSerializer, ProcessSerializer, ProductSerializer, 
    ProductMaterialSerializer, MaterialSerializer,
    WorkOrderListSerializer, WorkOrderDetailSerializer,
    WorkOrderCreateUpdateSerializer, WorkOrderProcessSerializer,
    WorkOrderMaterialSerializer, WorkOrderProductSerializer, ProcessLogSerializer,
    WorkOrderProcessUpdateSerializer,
    ArtworkSerializer, ArtworkProductSerializer,
    DieSerializer, DieProductSerializer, FoilingPlateSerializer, FoilingPlateProductSerializer,
    EmbossingPlateSerializer, EmbossingPlateProductSerializer,
    WorkOrderTaskSerializer, ProductGroupSerializer, ProductGroupItemSerializer,
    TaskAssignmentRuleSerializer, NotificationSerializer
)


class CustomerViewSet(viewsets.ModelViewSet):
    """客户视图集"""
    queryset = Customer.objects.all()
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与施工单权限逻辑一致
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'contact_person', 'phone']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        根据用户权限过滤查询集：
        - 如果有 change_customer 权限，返回所有客户
        - 如果是业务员，只返回自己负责的客户
        - 如果有 view_customer 权限，返回所有客户（只读）
        """
        queryset = super().get_queryset()
        
        # 如果有编辑客户权限，返回所有客户
        if self.request.user.has_perm('workorder.change_customer'):
            return queryset.select_related('salesperson')
        
        # 如果是业务员，只返回自己负责的客户
        if self.request.user.groups.filter(name='业务员').exists():
            return queryset.filter(salesperson=self.request.user).select_related('salesperson')
        
        # 如果有查看客户权限，返回所有客户（只读）
        if self.request.user.has_perm('workorder.view_customer'):
            return queryset.select_related('salesperson')
        
        # 否则返回空查询集
        return queryset.none()


class DepartmentViewSet(viewsets.ModelViewSet):
    """部门视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'parent']
    search_fields = ['name', 'code']
    ordering_fields = ['sort_order', 'code']
    ordering = ['sort_order', 'code']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # 预加载关联数据，提高查询效率
        queryset = queryset.select_related('parent').prefetch_related('processes', 'children')
        return queryset


class ProcessViewSet(viewsets.ModelViewSet):
    """工序视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = Process.objects.all()
    serializer_class = ProcessSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_builtin']
    search_fields = ['name', 'code']
    ordering_fields = ['sort_order', 'code', 'created_at']
    ordering = ['sort_order', 'code']
    
    def destroy(self, request, *args, **kwargs):
        """删除工序，内置工序不可删除"""
        instance = self.get_object()
        if instance.is_builtin:
            return Response(
                {'error': '内置工序不可删除'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


class ProductViewSet(viewsets.ModelViewSet):
    """产品视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code', 'specification']
    ordering_fields = ['code', 'created_at']
    ordering = ['code']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related(
            'default_materials__material',
            'default_processes'
        )


class ProductMaterialViewSet(viewsets.ModelViewSet):
    """产品物料视图集"""
    queryset = ProductMaterial.objects.all()
    serializer_class = ProductMaterialSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product']
    ordering_fields = ['sort_order']
    ordering = ['product', 'sort_order']


class MaterialViewSet(viewsets.ModelViewSet):
    """物料视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'specification']
    ordering_fields = ['code', 'created_at']
    ordering = ['code']


class WorkOrderFilter(FilterSet):
    """施工单筛选器"""
    customer__salesperson = NumberFilter(field_name='customer__salesperson', lookup_expr='exact')
    
    class Meta:
        model = WorkOrder
        fields = ['status', 'priority', 'customer', 'manager', 'approval_status', 'customer__salesperson']


class WorkOrderViewSet(viewsets.ModelViewSet):
    """施工单视图集"""
    queryset = WorkOrder.objects.all()
    # permission_classes 继承自 settings 中的 DEFAULT_PERMISSION_CLASSES (DjangoModelPermissions)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = WorkOrderFilter
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
        """重写update方法以捕获详细错误信息"""
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            import traceback
            print(f"Error in WorkOrderViewSet.update: {str(e)}")
            print(traceback.format_exc())
            raise
    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.select_related('customer', 'customer__salesperson', 'manager', 'created_by', 'approved_by')
        queryset = queryset.prefetch_related('order_processes', 'materials', 'products__product', 'artworks', 'dies')
        return queryset
    
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
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """业务员审核施工单（完善版）"""
        from .models import WorkOrderApprovalLog
        
        work_order = self.get_object()
        
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
        if work_order.approval_status != 'pending':
            return Response(
                {'error': '该施工单已经审核过了，不能重复审核。如需重新审核，请先修改施工单并重新提交审核。'},
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
        from .models import WorkOrderTask, WorkOrderProcess
        
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
        from .models import WorkOrderProduct
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
                from .models import TaskLog
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
        from .models import TaskLog
        
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
                from .models import Department
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
    

class WorkOrderTaskFilter(FilterSet):
    """任务筛选器"""
    work_order_process = NumberFilter(field_name='work_order_process')
    process = NumberFilter(field_name='work_order_process__process', help_text='按工序筛选')
    status = CharFilter(field_name='status')
    task_type = CharFilter(field_name='task_type')
    assigned_department = NumberFilter(field_name='assigned_department', help_text='按分派部门筛选')
    assigned_operator = NumberFilter(field_name='assigned_operator', help_text='按分派操作员筛选')
    
    class Meta:
        model = WorkOrderTask
        fields = ['work_order_process', 'process', 'status', 'task_type', 'assigned_department', 'assigned_operator']


class WorkOrderTaskViewSet(viewsets.ModelViewSet):
    """施工单任务视图集"""
    queryset = WorkOrderTask.objects.select_related(
        'work_order_process', 'work_order_process__process', 
        'work_order_process__work_order', 'artwork', 'die', 'product', 'material',
        'foiling_plate', 'embossing_plate', 'assigned_department', 'assigned_operator',
        'parent_task'
    ).prefetch_related('logs', 'logs__operator', 'subtasks')
    serializer_class = WorkOrderTaskSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = WorkOrderTaskFilter
    search_fields = ['work_content', 'production_requirements']
    ordering_fields = ['created_at', 'updated_at', 'assigned_department', 'assigned_operator']
    ordering = ['-created_at']
    
    def perform_update(self, serializer):
        """更新任务时，检查工序是否完成"""
        task = serializer.save()
        
        # 验证完成数量不能超过生产数量
        if task.quantity_completed is not None and task.production_quantity:
            if task.quantity_completed > task.production_quantity:
                from rest_framework.exceptions import ValidationError
                raise ValidationError(f'完成数量（{task.quantity_completed}）不能超过生产数量（{task.production_quantity}）')
        
        # 如果任务完成，检查工序是否完成
        if task.status == 'completed':
            task.work_order_process.check_and_update_status()
    
    @action(detail=True, methods=['post'])
    def update_quantity(self, request, pk=None):
        """更新任务数量（包含业务条件验证，根据数量自动判断状态，记录操作人）"""
        from .models import TaskLog
        
        task = self.get_object()
        from .process_codes import ProcessCodes
        
        # 并发控制：检查版本号（乐观锁）
        expected_version = request.data.get('version')
        if expected_version is not None:
            if task.version != expected_version:
                return Response(
                    {'error': '任务已被其他操作员更新，请刷新后重试', 'current_version': task.version},
                    status=status.HTTP_409_CONFLICT
                )
        
        work_order_process = task.work_order_process
        work_order = work_order_process.work_order
        process_code = work_order_process.process.code
        
        # 获取前端传递的数据
        quantity_increment = request.data.get('quantity_increment')
        quantity_defective = request.data.get('quantity_defective', 0)  # 不良品数量（增量或绝对值）
        notes = request.data.get('notes', '')
        artwork_ids = request.data.get('artwork_ids', [])
        die_ids = request.data.get('die_ids', [])
        
        if quantity_increment is None:
            return Response(
                {'error': '请提供本次完成数量'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 计算新的完成数量（增量更新）
        quantity_before = task.quantity_completed
        new_quantity_completed = quantity_before + quantity_increment
        
        # 业务条件验证：制版任务需图稿/刀模等已确认
        if task.task_type == 'plate_making':
            if task.artwork and not task.artwork.confirmed:
                return Response(
                    {'error': '图稿未确认，无法更新任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if task.die and not task.die.confirmed:
                return Response(
                    {'error': '刀模未确认，无法更新任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if task.foiling_plate and not task.foiling_plate.confirmed:
                return Response(
                    {'error': '烫金版未确认，无法更新任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if task.embossing_plate and not task.embossing_plate.confirmed:
                return Response(
                    {'error': '压凸版未确认，无法更新任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 业务条件验证：开料任务需物料状态满足条件
        if task.task_type == 'cutting' and task.material:
            work_order_material = work_order.materials.filter(material=task.material).first()
            if work_order_material:
                if ProcessCodes.requires_material_cut_status(process_code):
                    if work_order_material.purchase_status != 'cut':
                        return Response(
                            {'error': '物料未开料，无法更新开料任务'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
        
        # 验证增量数量
        if new_quantity_completed < 0:
            return Response(
                {'error': '更新后完成数量不能小于0'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if task.production_quantity and new_quantity_completed > task.production_quantity:
            return Response(
                {'error': f'更新后完成数量（{new_quantity_completed}）不能超过生产数量（{task.production_quantity}）'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 记录更新前的状态和数量
        status_before = task.status
        
        # 处理设计图稿/设计刀模任务
        # 注意：设计不属于施工单工序，设计任务通过其他系统管理
        # 以下逻辑用于兼容可能已存在的设计任务（手动创建或历史数据）
        is_design_task = '设计图稿' in task.work_content or '更新图稿' in task.work_content
        is_die_design_task = '设计刀模' in task.work_content or '更新刀模' in task.work_content
        
        if is_design_task:
            if not artwork_ids or len(artwork_ids) == 0:
                return Response(
                    {'error': '请至少选择一个图稿'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            from .models import Artwork
            artworks = Artwork.objects.filter(id__in=artwork_ids)
            if artworks.count() != len(artwork_ids):
                return Response(
                    {'error': '部分图稿不存在'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            work_order.artworks.add(*artworks)
            task.artwork = artworks.first()
        elif is_die_design_task:
            if not die_ids or len(die_ids) == 0:
                return Response(
                    {'error': '请至少选择一个刀模'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            from .models import Die
            dies = Die.objects.filter(id__in=die_ids)
            if dies.count() != len(die_ids):
                return Response(
                    {'error': '部分刀模不存在'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            work_order.dies.add(*dies)
            task.die = dies.first()
        
        # 更新任务数量（增量更新）
        task.quantity_completed = new_quantity_completed
        
        # 更新不良品数量（如果提供了）
        if quantity_defective is not None:
            # 如果quantity_defective是增量，则累加；如果是绝对值，则直接设置
            # 这里假设前端传递的是增量值，如果需要支持绝对值，可以添加参数
            task.quantity_defective = (task.quantity_defective or 0) + quantity_defective
        
        if notes:
            task.production_requirements = notes
        
        # 根据数量自动判断状态
        # 如果完成数量 >= 生产数量，状态自动标志为已完成
        # 否则为进行中
        if task.production_quantity and new_quantity_completed >= task.production_quantity:
            task.status = 'completed'
        else:
            # 如果任务还未开始，设置为进行中
            if task.status == 'pending':
                task.status = 'in_progress'
            # 如果任务已完成但数量不足，设置为进行中
            elif task.status == 'completed' and new_quantity_completed < task.production_quantity:
                task.status = 'in_progress'
        
        # 更新版本号（乐观锁）
        task.version += 1
        task.save()
        
        # 记录操作日志（增强协作追踪）
        defective_increment = quantity_defective if quantity_defective else 0
        TaskLog.objects.create(
            task=task,
            log_type='update_quantity',
            content=f'更新完成数量：{quantity_before} → {new_quantity_completed}，本次完成：{quantity_increment}，不良品：{defective_increment}，状态：{status_before} → {task.status}' + (f'，备注：{notes}' if notes else ''),
            quantity_before=quantity_before,
            quantity_after=new_quantity_completed,
            quantity_increment=quantity_increment,
            quantity_defective_increment=defective_increment,
            status_before=status_before,
            status_after=task.status,
            operator=request.user
        )
        
        # 如果是子任务，更新父任务
        if task.is_subtask() and task.parent_task:
            task.parent_task.update_from_subtasks()
        
        # 检查工序是否完成
        task.work_order_process.check_and_update_status()
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """强制完成任务（用于完成数量小于生产数量但需要强制标志为已完成的情况）"""
        from .models import TaskLog
        
        task = self.get_object()
        from .process_codes import ProcessCodes
        
        # 并发控制：检查版本号（乐观锁）
        expected_version = request.data.get('version')
        if expected_version is not None:
            if task.version != expected_version:
                return Response(
                    {'error': '任务已被其他操作员更新，请刷新后重试', 'current_version': task.version},
                    status=status.HTTP_409_CONFLICT
                )
        
        work_order_process = task.work_order_process
        work_order = work_order_process.work_order
        process_code = work_order_process.process.code
        
        # 获取前端传递的数据
        completion_reason = request.data.get('completion_reason', '')
        quantity_defective = request.data.get('quantity_defective', 0)  # 不良品数量
        notes = request.data.get('notes', '')
        artwork_ids = request.data.get('artwork_ids', [])
        die_ids = request.data.get('die_ids', [])
        
        # 业务条件验证：制版任务需图稿/刀模等已确认
        if task.task_type == 'plate_making' and task.artwork:
            if not task.artwork.confirmed:
                return Response(
                    {'error': '图稿未确认，无法完成任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 业务条件验证：制版任务需图稿/刀模等已确认
        if task.task_type == 'plate_making':
            if task.artwork and not task.artwork.confirmed:
                return Response(
                    {'error': '图稿未确认，无法完成任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if task.die and not task.die.confirmed:
                return Response(
                    {'error': '刀模未确认，无法完成任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if task.foiling_plate and not task.foiling_plate.confirmed:
                return Response(
                    {'error': '烫金版未确认，无法完成任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if task.embossing_plate and not task.embossing_plate.confirmed:
                return Response(
                    {'error': '压凸版未确认，无法完成任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 业务条件验证：开料任务需物料状态满足条件
        if task.task_type == 'cutting' and task.material:
            work_order_material = work_order.materials.filter(material=task.material).first()
            if work_order_material:
                if ProcessCodes.requires_material_cut_status(process_code):
                    if work_order_material.purchase_status != 'cut':
                        return Response(
                            {'error': '物料未开料，无法完成开料任务'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
        
        # 记录更新前的状态和数量
        status_before = task.status
        quantity_before = task.quantity_completed
        
        # 处理设计图稿/设计刀模任务
        # 注意：设计不属于施工单工序，设计任务通过其他系统管理
        # 以下逻辑用于兼容可能已存在的设计任务（手动创建或历史数据）
        is_design_task = '设计图稿' in task.work_content or '更新图稿' in task.work_content
        is_die_design_task = '设计刀模' in task.work_content or '更新刀模' in task.work_content
        
        if is_design_task:
            if not artwork_ids or len(artwork_ids) == 0:
                return Response(
                    {'error': '请至少选择一个图稿'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            from .models import Artwork
            artworks = Artwork.objects.filter(id__in=artwork_ids)
            if artworks.count() != len(artwork_ids):
                return Response(
                    {'error': '部分图稿不存在'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            work_order.artworks.add(*artworks)
            task.artwork = artworks.first()
        elif is_die_design_task:
            if not die_ids or len(die_ids) == 0:
                return Response(
                    {'error': '请至少选择一个刀模'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            from .models import Die
            dies = Die.objects.filter(id__in=die_ids)
            if dies.count() != len(die_ids):
                return Response(
                    {'error': '部分刀模不存在'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            work_order.dies.add(*dies)
            task.die = dies.first()
        
        # 强制设置为已完成（不根据数量判断）
        task.status = 'completed'
        if notes:
            task.production_requirements = notes
        
        # 制版任务：完成数量固定为1
        if task.task_type == 'plate_making':
            task.quantity_completed = 1
        
        # 更新不良品数量（如果提供了）
        if quantity_defective is not None:
            task.quantity_defective = quantity_defective
        
        # 更新版本号（乐观锁）
        task.version += 1
        task.save()
        
        # 计算数量增量
        quantity_increment = task.quantity_completed - quantity_before
        defective_increment = quantity_defective if quantity_defective else 0
        
        # 记录操作日志（增强协作追踪）
        log_content = f'强制完成任务，完成数量：{quantity_before} → {task.quantity_completed}，不良品：{defective_increment}，状态：{status_before} → completed'
        if quantity_increment != 0:
            log_content += f'，本次完成：{quantity_increment}'
        if completion_reason:
            log_content += f'，完成理由：{completion_reason}'
        if notes:
            log_content += f'，备注：{notes}'
        
        TaskLog.objects.create(
            task=task,
            log_type='complete',
            content=log_content,
            quantity_before=quantity_before,
            quantity_after=task.quantity_completed,
            quantity_increment=quantity_increment,
            quantity_defective_increment=defective_increment,
            status_before=status_before,
            status_after='completed',
            completion_reason=completion_reason,
            operator=request.user
        )
        
        # 如果是子任务，更新父任务
        if task.is_subtask() and task.parent_task:
            task.parent_task.update_from_subtasks()
        
        # 检查工序是否完成
        task.work_order_process.check_and_update_status()
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def split(self, request, pk=None):
        """拆分任务为多个子任务（支持多人协作）
        
        请求参数：
        - splits: 子任务列表，每个子任务包含：
          - production_quantity: 生产数量
          - assigned_department: 分派部门ID（可选）
          - assigned_operator: 分派操作员ID（可选）
          - work_content: 工作内容（可选，默认使用父任务内容）
        """
        from .models import WorkOrderTask, TaskLog
        
        task = self.get_object()
        
        # 检查任务是否已经拆分
        if task.subtasks.exists():
            return Response(
                {'error': '该任务已经拆分，无法再次拆分'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查任务是否已完成
        if task.status == 'completed':
            return Response(
                {'error': '已完成的任务无法拆分'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        splits = request.data.get('splits', [])
        if not splits or len(splits) < 2:
            return Response(
                {'error': '至少需要拆分为2个子任务'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 验证拆分数量总和不超过父任务数量
        total_split_quantity = sum(s.get('production_quantity', 0) for s in splits)
        if total_split_quantity > task.production_quantity:
            return Response(
                {'error': f'子任务数量总和（{total_split_quantity}）不能超过父任务数量（{task.production_quantity}）'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 创建子任务
        created_subtasks = []
        for idx, split_data in enumerate(splits):
            production_quantity = split_data.get('production_quantity', 0)
            if production_quantity <= 0:
                return Response(
                    {'error': f'第{idx+1}个子任务的生产数量必须大于0'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 获取分派信息
            assigned_department_id = split_data.get('assigned_department')
            assigned_operator_id = split_data.get('assigned_operator')
            work_content = split_data.get('work_content', f"{task.work_content}（子任务{idx+1}）")
            
            # 创建子任务
            subtask = WorkOrderTask.objects.create(
                work_order_process=task.work_order_process,
                task_type=task.task_type,
                work_content=work_content,
                production_quantity=production_quantity,
                quantity_completed=0,
                quantity_defective=0,
                parent_task=task,
                assigned_department_id=assigned_department_id,
                assigned_operator_id=assigned_operator_id,
                artwork=task.artwork,
                die=task.die,
                product=task.product,
                material=task.material,
                foiling_plate=task.foiling_plate,
                embossing_plate=task.embossing_plate,
                production_requirements=task.production_requirements,
                status='pending',
                auto_calculate_quantity=task.auto_calculate_quantity
            )
            created_subtasks.append(subtask)
        
        # 将父任务状态设置为进行中（因为已拆分）
        if task.status == 'pending':
            task.status = 'in_progress'
            task.version += 1
            task.save()
        
        # 记录拆分日志
        TaskLog.objects.create(
            task=task,
            log_type='status_change',
            content=f'任务已拆分为{len(created_subtasks)}个子任务，子任务数量总和：{total_split_quantity}',
            operator=request.user
        )
        
        serializer = self.get_serializer(task)
        return Response({
            'message': f'任务已成功拆分为{len(created_subtasks)}个子任务',
            'parent_task': serializer.data,
            'subtasks_count': len(created_subtasks)
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """分派任务到部门和操作员（支持调整分派）
        
        使用场景：
        - 自动分派后需要调整（如从包装车间调整为外协车间）
        - 手动调整任务分派
        - 记录调整原因和备注
        """
        from .models import TaskLog
        
        task = self.get_object()
        department_id = request.data.get('assigned_department')
        operator_id = request.data.get('assigned_operator')
        reason = request.data.get('reason', '')  # 调整原因
        notes = request.data.get('notes', '')  # 备注
        
        # 记录调整前的状态
        old_department = task.assigned_department
        old_operator = task.assigned_operator
        changes = []
        
        # 更新分派部门
        if department_id is not None:
            if department_id:
                try:
                    from .models import Department
                    department = Department.objects.get(id=department_id)
                    if task.assigned_department != department:
                        changes.append(f'部门：{old_department.name if old_department else "未分配"} → {department.name}')
                        task.assigned_department = department
                except Department.DoesNotExist:
                    return Response(
                        {'error': '部门不存在'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                if task.assigned_department:
                    changes.append(f'部门：{old_department.name if old_department else "未分配"} → 未分配')
                    task.assigned_department = None
        
        # 更新分派操作员
        if operator_id is not None:
            if operator_id:
                try:
                    from django.contrib.auth.models import User
                    operator = User.objects.get(id=operator_id)
                    old_operator_name = f"{old_operator.first_name}{old_operator.last_name}" if old_operator else "未分配"
                    new_operator_name = f"{operator.first_name}{operator.last_name}"
                    if task.assigned_operator != operator:
                        changes.append(f'操作员：{old_operator_name} → {new_operator_name}')
                        task.assigned_operator = operator
                except User.DoesNotExist:
                    return Response(
                        {'error': '操作员不存在'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                if task.assigned_operator:
                    old_operator_name = f"{old_operator.first_name}{old_operator.last_name}" if old_operator else "未分配"
                    changes.append(f'操作员：{old_operator_name} → 未分配')
                    task.assigned_operator = None
        
        # 如果有变更，保存并记录日志
        if changes:
            task.save()
            
            # 记录调整日志
            log_content = f'调整任务分派：{", ".join(changes)}'
            if reason:
                log_content += f'，原因：{reason}'
            if notes:
                log_content += f'，备注：{notes}'
            
            TaskLog.objects.create(
                task=task,
                log_type='status_change',
                content=log_content,
                operator=request.user
            )
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消任务
        
        请求参数：
        - cancellation_reason: 取消原因（必填）
        - notes: 备注（可选）
        
        权限控制：
        - 只有生产主管、创建人或任务分派的操作员可以取消任务
        - 已开始的任务需要特殊权限才能取消
        """
        from .models import TaskLog
        from django.contrib.auth.models import User
        
        task = self.get_object()
        cancellation_reason = request.data.get('cancellation_reason', '').strip()
        notes = request.data.get('notes', '')
        
        # 验证取消原因
        if not cancellation_reason:
            return Response(
                {'error': '请填写取消原因'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查任务状态
        if task.status == 'cancelled':
            return Response(
                {'error': '任务已经取消，无法重复取消'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if task.status == 'completed':
            return Response(
                {'error': '已完成的任务无法取消'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 权限检查：生产主管、创建人或任务分派的操作员可以取消
        # 这里简化处理，实际可以根据用户角色和部门进行更细粒度的控制
        user = request.user
        can_cancel = False
        
        # 检查是否为生产主管（简化：检查用户是否有管理权限）
        if user.has_perm('workorder.change_workorder'):
            can_cancel = True
        # 检查是否为任务分派的操作员
        elif task.assigned_operator == user:
            can_cancel = True
        # 检查是否为施工单创建人
        elif task.work_order_process.work_order.created_by == user:
            can_cancel = True
        
        if not can_cancel:
            return Response(
                {'error': '您没有权限取消此任务'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 检查是否会影响工序完成状态
        work_order_process = task.work_order_process
        # 如果工序只有一个任务且该任务被取消，工序无法完成
        if work_order_process.tasks.count() == 1:
            # 如果工序状态不是pending，需要特殊处理
            if work_order_process.status != 'pending':
                return Response(
                    {'error': '该任务是工序的唯一任务，取消后工序无法完成。请先处理工序状态'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 记录取消前的状态
        status_before = task.status
        quantity_before = task.quantity_completed
        
        # 取消任务
        task.status = 'cancelled'
        task.version += 1
        task.save()
        
        # 记录操作日志
        log_content = f'取消任务，原因：{cancellation_reason}'
        if notes:
            log_content += f'，备注：{notes}'
        
        TaskLog.objects.create(
            task=task,
            log_type='status_change',
            content=log_content,
            status_before=status_before,
            status_after='cancelled',
            operator=user
        )
        
        # 创建任务取消通知
        if task.assigned_operator:
            Notification.create_notification(
                recipient=task.assigned_operator,
                notification_type='task_cancelled',
                title=f'任务已取消：{task.work_content}',
                content=f'任务"{task.work_content}"已被取消。取消原因：{cancellation_reason}',
                priority='normal',
                work_order=work_order_process.work_order,
                work_order_process=work_order_process,
                task=task
            )
        
        # 检查工序状态：如果所有任务都取消或完成，需要更新工序状态
        remaining_tasks = work_order_process.tasks.exclude(status='cancelled')
        if not remaining_tasks.exists():
            # 所有任务都已取消或完成，工序状态需要调整
            if work_order_process.status == 'in_progress':
                # 如果工序进行中但没有可用任务，可能需要暂停或取消工序
                # 这里暂时不自动处理，由用户手动处理
                pass
        
        serializer = self.get_serializer(task)
        return Response({
            'message': '任务已成功取消',
            'task': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def assignment_history(self, request):
        """分派历史查询：查询任务分派调整历史记录"""
        from .models import TaskLog
        from django.db.models import Q
        
        # 获取查询参数
        task_id = request.query_params.get('task_id')
        department_id = request.query_params.get('department_id')
        operator_id = request.query_params.get('operator_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # 构建查询条件：筛选包含"调整任务分派"的日志
        query = Q(log_type='status_change', content__contains='调整任务分派')
        
        if task_id:
            query &= Q(task_id=task_id)
        
        if department_id:
            # 通过任务查询部门
            query &= Q(task__assigned_department_id=department_id)
        
        if operator_id:
            # 通过任务或日志操作员查询
            query &= (Q(task__assigned_operator_id=operator_id) | Q(operator_id=operator_id))
        
        if start_date:
            try:
                from datetime import datetime
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                query &= Q(created_at__gte=start_date_obj)
            except ValueError:
                pass
        
        if end_date:
            try:
                from datetime import datetime, timedelta
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query &= Q(created_at__lt=end_date_obj)
            except ValueError:
                pass
        
        # 查询日志
        logs = TaskLog.objects.filter(query).select_related(
            'task', 'task__assigned_department', 'task__assigned_operator',
            'operator', 'task__work_order_process', 'task__work_order_process__work_order'
        ).order_by('-created_at')
        
        # 分页
        total = logs.count()
        start = (page - 1) * page_size
        end = start + page_size
        logs = logs[start:end]
        
        # 序列化结果
        from .serializers import TaskLogSerializer
        serializer = TaskLogSerializer()
        
        # 构建响应数据，包含额外信息
        results = []
        for log in logs:
            log_data = serializer.to_representation(log)
            # 添加任务和施工单信息
            if log.task:
                log_data['task_info'] = {
                    'id': log.task.id,
                    'work_content': log.task.work_content,
                    'assigned_department': log.task.assigned_department.name if log.task.assigned_department else None,
                    'assigned_operator': log.task.assigned_operator.username if log.task.assigned_operator else None,
                }
                if log.task.work_order_process and log.task.work_order_process.work_order:
                    wo = log.task.work_order_process.work_order
                    log_data['work_order_info'] = {
                        'id': wo.id,
                        'order_number': wo.order_number,
                        'customer_name': wo.customer.name if wo.customer else None,
                    }
            # 添加操作员名称
            if log.operator:
                log_data['operator_name'] = log.operator.username
            results.append(log_data)
        
        return Response({
            'results': results,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        })
    
    @action(detail=False, methods=['get'])
    def collaboration_stats(self, request):
        """协作统计：按操作员汇总完成任务数量、完成时间、不良品率等"""
        from django.contrib.auth.models import User
        from django.db.models import Count, Sum, Avg, Q, F
        from datetime import datetime, timedelta
        
        # 获取查询参数
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        department_id = request.query_params.get('department_id')
        
        # 构建时间过滤条件
        time_filter = Q()
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                time_filter &= Q(logs__created_at__gte=start_date_obj)
            except ValueError:
                pass
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                time_filter &= Q(logs__created_at__lt=end_date_obj)
            except ValueError:
                pass
        
        # 构建部门过滤条件
        dept_filter = Q()
        if department_id:
            dept_filter = Q(assigned_department_id=department_id)
        
        # 获取所有有任务的操作员
        operators = User.objects.filter(
            assigned_tasks__isnull=False,
            is_active=True
        ).exclude(
            is_superuser=True
        ).distinct()
        
        if department_id:
            operators = operators.filter(profile__departments__id=department_id).distinct()
        
        stats_list = []
        for operator in operators:
            # 获取该操作员的任务
            task_filter = Q(assigned_operator=operator) & dept_filter
            tasks = WorkOrderTask.objects.filter(task_filter)
            
            # 统计总数
            total_tasks = tasks.count()
            completed_tasks = tasks.filter(status='completed').count()
            in_progress_tasks = tasks.filter(status='in_progress').count()
            pending_tasks = tasks.filter(status='pending').count()
            
            # 统计完成数量和不良品数量（只统计已完成的任务）
            completed_task_data = tasks.filter(
                Q(status='completed') & time_filter
            ).aggregate(
                total_completed_quantity=Sum('quantity_completed', default=0),
                total_defective_quantity=Sum('quantity_defective', default=0),
                total_production_quantity=Sum('production_quantity', default=0)
            )
            
            total_completed_quantity = completed_task_data['total_completed_quantity'] or 0
            total_defective_quantity = completed_task_data['total_defective_quantity'] or 0
            total_production_quantity = completed_task_data['total_production_quantity'] or 0
            
            # 计算不良品率
            defective_rate = 0
            if total_completed_quantity > 0:
                defective_rate = round((total_defective_quantity / total_completed_quantity) * 100, 2)
            
            # 统计平均完成时间（从任务创建到完成的时间）
            avg_completion_hours = None
            completed_tasks_with_times = tasks.filter(
                status='completed',
                created_at__isnull=False
            ).filter(time_filter)
            
            if completed_tasks_with_times.exists():
                # 计算平均完成时间（小时）
                completion_times = []
                for task in completed_tasks_with_times:
                    completion_log = task.logs.filter(log_type='complete').first()
                    if completion_log and task.created_at:
                        duration = completion_log.created_at - task.created_at
                        completion_times.append(duration.total_seconds() / 3600)  # 转换为小时
                
                if completion_times:
                    avg_completion_hours = round(sum(completion_times) / len(completion_times), 2)
            
            # 获取操作员所属部门
            departments = operator.profile.departments.all() if hasattr(operator, 'profile') else []
            dept_names = [dept.name for dept in departments]
            
            stats_list.append({
                'operator_id': operator.id,
                'operator_username': operator.username,
                'operator_name': operator.get_full_name() or operator.username,
                'departments': dept_names,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'in_progress_tasks': in_progress_tasks,
                'pending_tasks': pending_tasks,
                'total_completed_quantity': total_completed_quantity,
                'total_defective_quantity': total_defective_quantity,
                'total_production_quantity': total_production_quantity,
                'defective_rate': defective_rate,
                'avg_completion_hours': avg_completion_hours,
                'completion_rate': round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 2)
            })
        
        # 按完成数量排序（降序）
        stats_list.sort(key=lambda x: x['total_completed_quantity'], reverse=True)
        
        return Response({
            'results': stats_list,
            'summary': {
                'total_operators': len(stats_list),
                'total_tasks': sum(s['total_tasks'] for s in stats_list),
                'total_completed_tasks': sum(s['completed_tasks'] for s in stats_list),
                'total_completed_quantity': sum(s['total_completed_quantity'] for s in stats_list),
                'total_defective_quantity': sum(s['total_defective_quantity'] for s in stats_list),
                'overall_defective_rate': round(
                    (sum(s['total_defective_quantity'] for s in stats_list) / 
                     sum(s['total_completed_quantity'] for s in stats_list) * 100)
                    if sum(s['total_completed_quantity'] for s in stats_list) > 0 else 0, 
                    2
                )
            }
        })


class WorkOrderProductViewSet(viewsets.ModelViewSet):
    """施工单产品视图集"""
    queryset = WorkOrderProduct.objects.select_related('product', 'work_order')
    serializer_class = WorkOrderProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['work_order', 'product']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['work_order', 'sort_order']


class ProductGroupViewSet(viewsets.ModelViewSet):
    """产品组视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = ProductGroup.objects.prefetch_related('items__product')
    serializer_class = ProductGroupSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['code', 'created_at']
    ordering = ['code']


class ProductGroupItemViewSet(viewsets.ModelViewSet):
    """产品组子项视图集"""
    queryset = ProductGroupItem.objects.select_related('product_group', 'product')
    serializer_class = ProductGroupItemSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product_group', 'product']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['product_group', 'sort_order']


class WorkOrderMaterialViewSet(viewsets.ModelViewSet):
    """施工单物料视图集"""
    queryset = WorkOrderMaterial.objects.all()
    permission_classes = [WorkOrderMaterialPermission]  # 使用自定义权限：如果有编辑施工单权限，就可以编辑其物料
    serializer_class = WorkOrderMaterialSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['work_order', 'material']


class ProcessLogViewSet(viewsets.ReadOnlyModelViewSet):
    """工序日志视图集（只读）"""
    queryset = ProcessLog.objects.all()
    serializer_class = ProcessLogSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['work_order_process', 'log_type', 'operator']
    ordering_fields = ['created_at']
    ordering = ['-created_at']


class ArtworkViewSet(viewsets.ModelViewSet):
    """图稿视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = Artwork.objects.all()
    serializer_class = ArtworkSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['base_code', 'version']
    search_fields = ['base_code', 'name', 'imposition_size']
    ordering_fields = ['created_at', 'base_code', 'version', 'name']
    ordering = ['-base_code', '-version']
    
    @action(detail=True, methods=['post'])
    def create_version(self, request, pk=None):
        """基于现有图稿创建新版本"""
        original_artwork = self.get_object()
        
        # 获取下一个版本号
        next_version = Artwork.get_next_version(original_artwork.base_code)
        
        # 创建新版本，复制原图稿的所有信息
        new_artwork = Artwork.objects.create(
            base_code=original_artwork.base_code,
            version=next_version,
            name=original_artwork.name,
            cmyk_colors=original_artwork.cmyk_colors.copy() if original_artwork.cmyk_colors else [],
            other_colors=original_artwork.other_colors.copy() if original_artwork.other_colors else [],
            imposition_size=original_artwork.imposition_size,
            notes=original_artwork.notes
        )
        
        # 复制关联的刀模
        new_artwork.dies.set(original_artwork.dies.all())
        
        # 复制关联的产品
        for ap in original_artwork.products.all():
            ArtworkProduct.objects.create(
                artwork=new_artwork,
                product=ap.product,
                imposition_quantity=ap.imposition_quantity,
                sort_order=ap.sort_order
            )
        
        serializer = self.get_serializer(new_artwork)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """设计部确认图稿"""
        artwork = self.get_object()
        
        if artwork.confirmed:
            return Response(
                {'error': '该图稿已经确认过了'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        artwork.confirmed = True
        artwork.confirmed_by = request.user
        artwork.confirmed_at = timezone.now()
        artwork.save()
        
        # 检查相关的制版工序任务是否全部完成
        # 找到所有包含该图稿的任务
        tasks = WorkOrderTask.objects.filter(
            artwork=artwork,
            task_type='artwork',
            work_order_process__status='in_progress'
        )
        
        for task in tasks:
            # 如果图稿已确认，可以标记任务为完成
            if task.artwork.confirmed:
                task.status = 'completed'
                task.quantity_completed = 1
                task.save()
                
                # 检查工序是否完成
                task.work_order_process.check_and_update_status()
        
        serializer = self.get_serializer(artwork)
        return Response(serializer.data)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related('products__product')


class ArtworkProductViewSet(viewsets.ModelViewSet):
    """图稿产品视图集"""
    queryset = ArtworkProduct.objects.all()
    serializer_class = ArtworkProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['artwork', 'product']
    ordering_fields = ['sort_order']
    ordering = ['artwork', 'sort_order']


class DieViewSet(viewsets.ModelViewSet):
    """刀模视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = Die.objects.all()
    serializer_class = DieSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = []
    search_fields = ['code', 'name', 'size', 'material']
    ordering_fields = ['created_at', 'code', 'name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related('products__product')


class DieProductViewSet(viewsets.ModelViewSet):
    """刀模产品视图集"""
    queryset = DieProduct.objects.all()
    serializer_class = DieProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['die', 'product']
    ordering_fields = ['sort_order']
    ordering = ['die', 'sort_order']


class FoilingPlateViewSet(viewsets.ModelViewSet):
    """烫金版视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = FoilingPlate.objects.all()
    serializer_class = FoilingPlateSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = []
    search_fields = ['code', 'name', 'size', 'material']
    ordering_fields = ['created_at', 'code', 'name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related('products__product')


class FoilingPlateProductViewSet(viewsets.ModelViewSet):
    """烫金版产品视图集"""
    queryset = FoilingPlateProduct.objects.all()
    serializer_class = FoilingPlateProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['foiling_plate', 'product']
    ordering_fields = ['sort_order']
    ordering = ['foiling_plate', 'sort_order']


class EmbossingPlateViewSet(viewsets.ModelViewSet):
    """压凸版视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = EmbossingPlate.objects.all()
    serializer_class = EmbossingPlateSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = []
    search_fields = ['code', 'name', 'size', 'material']
    ordering_fields = ['created_at', 'code', 'name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related('products__product')


class EmbossingPlateProductViewSet(viewsets.ModelViewSet):
    """压凸版产品视图集"""
    queryset = EmbossingPlateProduct.objects.all()
    serializer_class = EmbossingPlateProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['embossing_plate', 'product']
    ordering_fields = ['sort_order']
    ordering = ['embossing_plate', 'sort_order']


class TaskAssignmentRuleViewSet(viewsets.ModelViewSet):
    """任务分派规则视图集"""
    queryset = TaskAssignmentRule.objects.select_related('process', 'department').all()
    serializer_class = TaskAssignmentRuleSerializer
    permission_classes = [DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['process', 'department', 'is_active']
    search_fields = ['process__name', 'process__code', 'department__name', 'department__code', 'notes']
    ordering_fields = ['priority', 'created_at', 'updated_at']
    ordering = ['process', '-priority', 'department']


class NotificationViewSet(viewsets.ModelViewSet):
    """通知视图集"""
    queryset = Notification.objects.all()  # 默认 queryset，会被 get_queryset() 覆盖
    serializer_class = NotificationSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'priority', 'is_read', 'work_order', 'task']
    ordering_fields = ['created_at', 'priority']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """只返回当前用户的通知"""
        queryset = Notification.objects.filter(recipient=self.request.user)
        # 过滤过期通知
        from django.utils import timezone
        queryset = queryset.filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
        )
        return queryset.select_related('work_order', 'work_order_process', 'task', 'recipient')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """标记通知为已读"""
        notification = self.get_object()
        notification.mark_as_read()
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """标记所有通知为已读"""
        count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'message': f'已标记 {count} 条通知为已读'})
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """获取未读通知数量"""
        count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
        return Response({'unread_count': count})

