"""
产品相关视图集

包含产品、产品物料、产品组等视图集。
"""

from ..models.products import Product, ProductGroup, ProductGroupItem, ProductMaterial
from ..serializers.products import (
    ProductGroupItemSerializer,
    ProductGroupSerializer,
    ProductMaterialSerializer,
    ProductSerializer,
)
from .base_viewsets import BaseViewSet


class ProductViewSet(BaseViewSet):
    """产品视图集"""

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_fields = ["is_active"]
    search_fields = ["name", "code", "specification"]
    ordering_fields = ["code", "created_at"]
    ordering = ["code"]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related(
            "default_materials__material", "default_processes"
        )


class ProductMaterialViewSet(BaseViewSet):
    """产品物料视图集"""

    queryset = ProductMaterial.objects.all()
    serializer_class = ProductMaterialSerializer
    filterset_fields = ["product"]
    ordering_fields = ["sort_order"]
    ordering = ["product", "sort_order"]


class ProductGroupViewSet(BaseViewSet):
    """产品组视图集"""

    queryset = ProductGroup.objects.prefetch_related("items__product")
    serializer_class = ProductGroupSerializer
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]
    ordering_fields = ["code", "created_at"]
    ordering = ["code"]


class ProductGroupItemViewSet(BaseViewSet):
    """产品组子项视图集"""

    queryset = ProductGroupItem.objects.select_related("product_group", "product")
    serializer_class = ProductGroupItemSerializer
    filterset_fields = ["product_group", "product"]
    ordering_fields = ["sort_order", "created_at"]
    ordering = ["product_group", "sort_order"]
