"""
产品相关视图集

包含产品、产品物料、产品组等视图集。
"""

from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import DjangoModelPermissions

from ..models.products import Product, ProductMaterial, ProductGroup, ProductGroupItem
from ..serializers.products import (
    ProductSerializer,
    ProductMaterialSerializer,
    ProductGroupSerializer,
    ProductGroupItemSerializer
)


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
    ordering_fields = ['sort_order']
    ordering = ['product', 'sort_order']
    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class ProductMaterialFilterSet(FilterSet):
            class Meta:
                model = ProductMaterial
                fields = ['product']

        return ProductMaterialFilterSet



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
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['product_group', 'sort_order']
    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class ProductGroupItemFilterSet(FilterSet):
            class Meta:
                model = ProductGroupItem
                fields = ['product_group', 'product']

        return ProductGroupItemFilterSet

