"""
物料相关视图集

包含物料、供应商、物料供应商等视图集。
"""

from rest_framework import viewsets, filters, pagination
from django_filters.rest_framework import DjangoFilterBackend
from ..permissions import SuperuserFriendlyModelPermissions

from ..models.materials import Material, Supplier, MaterialSupplier
from ..serializers.materials import MaterialSerializer, SupplierSerializer, MaterialSupplierSerializer


class MaterialViewSet(viewsets.ModelViewSet):
    """物料视图集"""
    permission_classes = [SuperuserFriendlyModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'specification']
    ordering_fields = ['code', 'created_at']
    ordering = ['code']



class SupplierViewSet(viewsets.ModelViewSet):
    """供应商视图集"""
    queryset = Supplier.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]
    serializer_class = SupplierSerializer
    pagination_class = pagination.PageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['name', 'code', 'contact_person', 'phone', 'email']
    ordering_fields = ['created_at', 'name', 'code']
    ordering = ['-created_at']



class MaterialSupplierViewSet(viewsets.ModelViewSet):
    """物料供应商关联视图集"""
    queryset = MaterialSupplier.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]
    serializer_class = MaterialSupplierSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['material', 'supplier', 'is_preferred']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

