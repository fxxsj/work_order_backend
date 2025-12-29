from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum
from django.utils import timezone
from .models import (
    Customer, Process, Material, WorkOrder,
    WorkOrderProcess, WorkOrderMaterial, ProcessLog
)
from .serializers import (
    CustomerSerializer, ProcessSerializer, MaterialSerializer,
    WorkOrderListSerializer, WorkOrderDetailSerializer,
    WorkOrderCreateUpdateSerializer, WorkOrderProcessSerializer,
    WorkOrderMaterialSerializer, ProcessLogSerializer,
    WorkOrderProcessUpdateSerializer
)


class CustomerViewSet(viewsets.ModelViewSet):
    """客户视图集"""
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'contact_person', 'phone']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']


class ProcessViewSet(viewsets.ModelViewSet):
    """工序视图集"""
    queryset = Process.objects.all()
    serializer_class = ProcessSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['sort_order', 'code', 'created_at']
    ordering = ['sort_order', 'code']


class MaterialViewSet(viewsets.ModelViewSet):
    """物料视图集"""
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'specification']
    ordering_fields = ['code', 'created_at']
    ordering = ['code']


class WorkOrderViewSet(viewsets.ModelViewSet):
    """施工单视图集"""
    queryset = WorkOrder.objects.all()
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
        queryset = queryset.select_related('customer', 'manager', 'created_by')
        queryset = queryset.prefetch_related('order_processes', 'materials')
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
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
        status_stats = queryset.values('status').annotate(count=Count('id'))
        priority_stats = queryset.values('priority').annotate(count=Count('id'))
        
        # 即将到期的订单（7天内）
        upcoming_deadline = queryset.filter(
            delivery_date__lte=timezone.now().date() + timezone.timedelta(days=7),
            status__in=['pending', 'in_progress']
        ).count()
        
        return Response({
            'total_count': total_count,
            'status_statistics': list(status_stats),
            'priority_statistics': list(priority_stats),
            'upcoming_deadline_count': upcoming_deadline,
        })


class WorkOrderProcessViewSet(viewsets.ModelViewSet):
    """施工单工序视图集"""
    queryset = WorkOrderProcess.objects.all()
    serializer_class = WorkOrderProcessSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['work_order', 'process', 'status', 'operator']
    search_fields = ['work_order__order_number', 'process__name']
    ordering_fields = ['sequence', 'actual_start_time', 'created_at']
    ordering = ['work_order', 'sequence']
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return WorkOrderProcessUpdateSerializer
        return WorkOrderProcessSerializer
    
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


class WorkOrderMaterialViewSet(viewsets.ModelViewSet):
    """施工单物料视图集"""
    queryset = WorkOrderMaterial.objects.all()
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

