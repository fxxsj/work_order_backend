"""
物料相关视图集

包含物料、供应商、物料供应商、采购单等视图集。
"""

from rest_framework import viewsets, filters, pagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Sum, Case, When, FloatField
from ..permissions import SuperuserFriendlyModelPermissions

from ..models.materials import Material, Supplier, MaterialSupplier, PurchaseOrder, PurchaseOrderItem
from ..serializers.materials import (
    MaterialSerializer,
    SupplierSerializer,
    MaterialSupplierSerializer,
    PurchaseOrderListSerializer,
    PurchaseOrderDetailSerializer,
    PurchaseOrderItemSerializer
)


class MaterialViewSet(viewsets.ModelViewSet):
    """物料视图集（优化版）"""
    permission_classes = [SuperuserFriendlyModelPermissions]
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'specification']
    ordering_fields = ['code', 'created_at', 'stock_quantity']
    ordering = ['code']

    def get_queryset(self):
        """优化查询性能"""
        queryset = super().get_queryset()
        return queryset.select_related(
            'default_supplier'
        )


class SupplierViewSet(viewsets.ModelViewSet):
    """供应商视图集（优化版）"""
    queryset = Supplier.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]
    serializer_class = SupplierSerializer
    pagination_class = pagination.PageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['name', 'code', 'contact_person', 'phone', 'email']
    ordering_fields = ['created_at', 'name', 'code']
    ordering = ['-created_at']

    def get_queryset(self):
        """优化查询性能：使用注解避免N+1查询"""
        queryset = super().get_queryset()
        # 使用注解预计算物料数量
        queryset = queryset.annotate(
            _material_count=Count('materialsupplier')
        )
        return queryset


class MaterialSupplierViewSet(viewsets.ModelViewSet):
    """物料供应商关联视图集"""
    queryset = MaterialSupplier.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]
    serializer_class = MaterialSupplierSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['material', 'supplier', 'is_preferred']
    ordering_fields = ['created_at']
    ordering = ['-created_at']


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """采购单视图集（优化版）"""
    queryset = PurchaseOrder.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['order_number', 'supplier__name']
    ordering_fields = ['created_at', 'order_number', 'total_amount']
    ordering = ['-created_at']

    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class PurchaseOrderFilterSet(FilterSet):
            class Meta:
                model = PurchaseOrder
                fields = ['supplier', 'status', 'work_order']

        return PurchaseOrderFilterSet

    def get_serializer_class(self):
        """根据 action 返回不同的序列化器"""
        if self.action == 'list':
            return PurchaseOrderListSerializer
        return PurchaseOrderDetailSerializer

    def get_queryset(self):
        """优化查询性能：使用注解避免N+1查询"""
        queryset = super().get_queryset()

        # 优化：预加载关联数据
        queryset = queryset.select_related(
            'supplier', 'submitted_by', 'approved_by', 'work_order'
        ).prefetch_related(
            'items__material'
        )

        # 优化：使用注解计算items_count和received_progress
        queryset = queryset.annotate(
            items_count=Count('items'),
            total_quantity=Sum('items__quantity'),
            total_received=Sum('items__received_quantity')
        )

        # 计算收货进度百分比
        queryset = queryset.annotate(
            received_progress=Case(
                When(total_quantity__gt=0, then=Sum('items__received_quantity') * 100.0 / Sum('items__quantity')),
                default=0.0,
                output_field=FloatField()
            )
        )

        return queryset


class PurchaseOrderItemViewSet(viewsets.ModelViewSet):
    """采购单明细视图集"""
    queryset = PurchaseOrderItem.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]
    serializer_class = PurchaseOrderItemSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['purchase_order', 'id']

    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class PurchaseOrderItemFilterSet(FilterSet):
            class Meta:
                model = PurchaseOrderItem
                fields = ['purchase_order', 'material', 'status']

        return PurchaseOrderItemFilterSet

    def get_queryset(self):
        """优化查询"""
        return super().get_queryset().select_related(
            'purchase_order', 'material', 'work_order_material'
        )

    def receive(self, request, pk=None):
        """单独收货某个明细"""
        from rest_framework.decorators import action
        from rest_framework.response import Response

        item = self.get_object()
        if item.purchase_order.status != 'ordered':
            return Response(
                {'detail': '只能收货已下单的采购单'},
                status=400
            )

        # 收货逻辑...
        return Response({'detail': '收货成功'})
