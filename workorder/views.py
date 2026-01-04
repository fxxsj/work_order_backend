from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import FilterSet, NumberFilter
from django.db.models import Q, Count, Sum, Max
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
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related('processes')


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
        """业务员审核施工单"""
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
        
        approval_status = request.data.get('approval_status')  # 'approved' 或 'rejected'
        approval_comment = request.data.get('approval_comment', '')
        
        if approval_status not in ['approved', 'rejected']:
            return Response(
                {'error': '审核状态必须是 approved 或 rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 更新审核信息
        work_order.approval_status = approval_status
        work_order.approved_by = request.user
        work_order.approved_at = timezone.now()
        work_order.approval_comment = approval_comment
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
        
        # 未审核施工单数量（仅业务员可见，只统计自己负责的）
        pending_approval_count = 0
        if request.user.groups.filter(name='业务员').exists():
            pending_approval_count = queryset.filter(
                approval_status='pending',
                customer__salesperson=request.user
            ).count()
        
        return Response({
            'total_count': total_count,
            'status_statistics': status_statistics,
            'priority_statistics': priority_statistics,
            'upcoming_deadline_count': upcoming_deadline,
            'pending_approval_count': pending_approval_count,
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
        """完成工序"""
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
        
        # 更新工序信息
        process.quantity_completed = quantity_completed
        process.quantity_defective = quantity_defective
        process.status = 'completed'
        process.actual_end_time = timezone.now()
        process.save()
        
        # 记录日志
        ProcessLog.objects.create(
            work_order_process=process,
            log_type='complete',
            content=f'完成工序，完成数量：{quantity_completed}，不良品数量：{quantity_defective}',
            operator=request.user
        )
        
        serializer = self.get_serializer(process)
        return Response(serializer.data)


class WorkOrderTaskViewSet(viewsets.ModelViewSet):
    """施工单任务视图集"""
    queryset = WorkOrderTask.objects.select_related(
        'work_order_process', 'work_order_process__process', 
        'work_order_process__work_order', 'artwork', 'die', 'product', 'material'
    )
    serializer_class = WorkOrderTaskSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['work_order_process', 'status', 'task_type']
    search_fields = ['work_content', 'production_requirements']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def perform_update(self, serializer):
        """更新任务时，检查工序是否完成"""
        task = serializer.save()
        
        # 如果任务完成，检查工序是否完成
        if task.status == 'completed':
            task.work_order_process.check_and_update_status()
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成任务（支持设计图稿任务时选择图稿）"""
        task = self.get_object()
        work_order = task.work_order_process.work_order
        
        # 检查任务内容是否包含"设计图稿"
        is_design_task = '设计图稿' in task.work_content
        is_die_design_task = '设计刀模' in task.work_content
        
        if is_design_task:
            # 设计图稿任务：需要选择图稿
            artwork_ids = request.data.get('artwork_ids', [])
            notes = request.data.get('notes', '')
            
            if not artwork_ids or len(artwork_ids) == 0:
                return Response(
                    {'error': '请至少选择一个图稿'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 验证图稿是否存在
            from .models import Artwork
            artworks = Artwork.objects.filter(id__in=artwork_ids)
            if artworks.count() != len(artwork_ids):
                return Response(
                    {'error': '部分图稿不存在'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 将图稿关联到施工单
            work_order.artworks.set(artworks)
            
            # 更新任务：关联第一个图稿（如果有多个图稿，关联第一个）
            task.artwork = artworks.first()
            task.production_requirements = notes  # 将备注保存到生产要求字段
            task.status = 'completed'
            if task.quantity_completed == 0:
                task.quantity_completed = task.production_quantity
            task.save()
            
            # 检查工序是否完成
            task.work_order_process.check_and_update_status()
            
            serializer = self.get_serializer(task)
            return Response(serializer.data)
        
        elif is_die_design_task:
            # 设计刀模任务：需要选择刀模
            die_ids = request.data.get('die_ids', [])
            notes = request.data.get('notes', '')
            
            if not die_ids or len(die_ids) == 0:
                return Response(
                    {'error': '请至少选择一个刀模'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 验证刀模是否存在
            from .models import Die
            dies = Die.objects.filter(id__in=die_ids)
            if dies.count() != len(die_ids):
                return Response(
                    {'error': '部分刀模不存在'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 将刀模关联到施工单
            work_order.dies.set(dies)
            
            # 更新任务：关联第一个刀模（如果有多个刀模，关联第一个）
            task.die = dies.first()
            task.production_requirements = notes  # 将备注保存到生产要求字段
            task.status = 'completed'
            if task.quantity_completed == 0:
                task.quantity_completed = task.production_quantity
            task.save()
            
            # 检查工序是否完成
            task.work_order_process.check_and_update_status()
            
            serializer = self.get_serializer(task)
            return Response(serializer.data)
        
        else:
            # 普通任务：直接完成
            notes = request.data.get('notes', '')
            task.production_requirements = notes  # 将备注保存到生产要求字段
            task.status = 'completed'
            if task.quantity_completed == 0:
                task.quantity_completed = task.production_quantity
            task.save()
            
            # 检查工序是否完成
            task.work_order_process.check_and_update_status()
            
            serializer = self.get_serializer(task)
            return Response(serializer.data)


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

