from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum
from django.utils import timezone
from .permissions import WorkOrderProcessPermission, WorkOrderMaterialPermission
from rest_framework.permissions import DjangoModelPermissions
from .models import (
    Customer, Department, Process, Product, ProductMaterial, Material, WorkOrder,
    WorkOrderProcess, WorkOrderMaterial, WorkOrderProduct, ProcessLog, Artwork, ArtworkProduct,
    Die, DieProduct, WorkOrderTask, ProductGroup, ProductGroupItem
)
from .serializers import (
    CustomerSerializer, DepartmentSerializer, ProcessSerializer, ProductSerializer, 
    ProductMaterialSerializer, MaterialSerializer,
    WorkOrderListSerializer, WorkOrderDetailSerializer,
    WorkOrderCreateUpdateSerializer, WorkOrderProcessSerializer,
    WorkOrderMaterialSerializer, WorkOrderProductSerializer, ProcessLogSerializer,
    WorkOrderProcessUpdateSerializer,
    ArtworkSerializer, ArtworkProductSerializer,
    DieSerializer, DieProductSerializer, WorkOrderTaskSerializer,
    ProductGroupSerializer, ProductGroupItemSerializer
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
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['sort_order', 'code']
    ordering = ['sort_order', 'code']


class ProcessViewSet(viewsets.ModelViewSet):
    """工序视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = Process.objects.all()
    serializer_class = ProcessSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['sort_order', 'code', 'created_at']
    ordering = ['sort_order', 'code']


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


class WorkOrderViewSet(viewsets.ModelViewSet):
    """施工单视图集"""
    queryset = WorkOrder.objects.all()
    # permission_classes 继承自 settings 中的 DEFAULT_PERMISSION_CLASSES (DjangoModelPermissions)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'customer', 'manager']
    search_fields = ['order_number', 'product_name', 'customer__name']
    ordering_fields = ['created_at', 'order_date', 'delivery_date', 'order_number']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return WorkOrderListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return WorkOrderCreateUpdateSerializer
        return WorkOrderDetailSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.select_related('customer', 'customer__salesperson', 'manager', 'created_by')
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
        planned_quantity = request.data.get('planned_quantity', 0)
        
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
            planned_quantity=planned_quantity
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
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """统计数据"""
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
            delivery_date__lte=timezone.now().date() + timezone.timedelta(days=7),
            status__in=['pending', 'in_progress']
        ).count()
        
        return Response({
            'total_count': total_count,
            'status_statistics': status_statistics,
            'priority_statistics': priority_statistics,
            'upcoming_deadline_count': upcoming_deadline,
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


class WorkOrderTaskViewSet(viewsets.ModelViewSet):
    """施工单任务视图集"""
    queryset = WorkOrderTask.objects.select_related('work_order_process')
    serializer_class = WorkOrderTaskSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['work_order_process', 'status']
    search_fields = ['work_content', 'production_requirements']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始工序"""
        process = self.get_object()
        
        if process.status == 'completed':
            return Response(
                {'error': '工序已完成，无法开始'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        process.status = 'in_progress'
        process.actual_start_time = timezone.now()
        process.operator = request.user
        process.save()
        
        # 记录日志
        ProcessLog.objects.create(
            work_order_process=process,
            log_type='start',
            content='开始工序',
            operator=request.user
        )
        
        serializer = self.get_serializer(process)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成工序"""
        process = self.get_object()
        
        if process.status == 'completed':
            return Response(
                {'error': '工序已完成'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        process.status = 'completed'
        process.actual_end_time = timezone.now()
        
        # 获取完成数量
        quantity_completed = request.data.get('quantity_completed')
        if quantity_completed:
            process.quantity_completed = quantity_completed
        
        quantity_defective = request.data.get('quantity_defective', 0)
        process.quantity_defective = quantity_defective
        
        process.calculate_duration()
        process.save()
        
        # 记录日志
        ProcessLog.objects.create(
            work_order_process=process,
            log_type='complete',
            content=f'完成工序，完成数量：{process.quantity_completed}，不良品：{process.quantity_defective}',
            operator=request.user
        )
        
        serializer = self.get_serializer(process)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_log(self, request, pk=None):
        """添加工序日志"""
        process = self.get_object()
        content = request.data.get('content')
        
        if not content:
            return Response(
                {'error': '请提供日志内容'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        log = ProcessLog.objects.create(
            work_order_process=process,
            log_type='note',
            content=content,
            operator=request.user
        )
        
        serializer = ProcessLogSerializer(log)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorkOrderTaskViewSet(viewsets.ModelViewSet):
    """施工单任务视图集"""
    queryset = WorkOrderTask.objects.select_related('work_order_process')
    serializer_class = WorkOrderTaskSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['work_order_process', 'status']
    search_fields = ['work_content', 'production_requirements']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']


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
    filterset_fields = ['color_count']
    search_fields = ['code', 'name', 'imposition_size']
    ordering_fields = ['created_at', 'code', 'name']
    ordering = ['-created_at']
    
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

