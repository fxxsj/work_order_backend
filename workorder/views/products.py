"""
产品相关视图集

包含产品、产品物料、产品组等视图集。
"""

from rest_framework import filters, permissions, status
from rest_framework.decorators import action

from ..import_export import export_model, import_model
from ..import_export_configs import (
    get_product_import_config,
    PRODUCT_EXPORT_CONFIG,
)
from ..models.products import (
    Product,
    ProductGroup,
    ProductGroupItem,
    ProductImage,
    ProductMaterial,
)
from ..response import APIResponse
from ..serializers.products import (
    ProductGroupItemSerializer,
    ProductGroupSerializer,
    ProductImageSerializer,
    ProductMaterialSerializer,
    ProductSerializer,
)
from .assets import ImageAssetActionsMixin
from .base_viewsets import BaseViewSet
from workorder.permissions import SuperuserFriendlyModelPermissions
from workorder.docs.products import (
    product_docs,
    product_group_docs,
    product_group_item_docs,
    product_material_docs,
)


@product_docs
class ProductViewSet(ImageAssetActionsMixin, BaseViewSet):
    """产品视图集"""

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    image_model = ProductImage
    image_serializer_class = ProductImageSerializer
    image_parent_field = "product"
    filterset_fields = ["is_active"]
    search_fields = ["name", "code", "specification"]
    permission_classes = [SuperuserFriendlyModelPermissions]
    ordering_fields = ["code", "created_at"]
    ordering = ["code"]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related(
            "default_materials__material", "default_processes", "images"
        )

    @action(detail=False, methods=["get"])
    def export(self, request):
        """导出产品列表 Excel"""
        queryset = self.get_queryset()
        return export_model(queryset, PRODUCT_EXPORT_CONFIG)

    @action(detail=False, methods=["post"])
    def import_products(self, request):
        """导入产品 Excel"""
        file = request.FILES.get('file')
        if not file:
            return APIResponse.error(
                "未上传文件",
                code=status.HTTP_400_BAD_REQUEST,
            )
        config = get_product_import_config(Product)
        result = import_model(file, config, request.user)
        if result['success_count'] == 0 and result['error_count'] > 0:
            return APIResponse.error(
                f"导入失败: {result['errors'][0] if result['errors'] else '未知错误'}",
                code=status.HTTP_400_BAD_REQUEST,
                data=result,
            )
        created = result.get('created_count', 0)
        updated = result.get('updated_count', 0)
        return APIResponse.success(
            message=f"导入完成: 新增 {created} 条, 更新 {updated} 条, 失败 {result['error_count']} 条",
            data=result,
        )


@product_material_docs
class ProductMaterialViewSet(BaseViewSet):
    """产品物料视图集"""

    queryset = ProductMaterial.objects.all()
    serializer_class = ProductMaterialSerializer
    filterset_fields = ["product"]
    ordering_fields = ["sort_order"]
    ordering = ["product", "sort_order"]


@product_group_docs
class ProductGroupViewSet(BaseViewSet):
    """产品组视图集"""

    queryset = ProductGroup.objects.prefetch_related("items__product")
    serializer_class = ProductGroupSerializer
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]
    ordering_fields = ["code", "created_at"]
    ordering = ["code"]


@product_group_item_docs
class ProductGroupItemViewSet(BaseViewSet):
    """产品组子项视图集"""

    queryset = ProductGroupItem.objects.select_related("product_group", "product")
    serializer_class = ProductGroupItemSerializer
    filterset_fields = ["product_group", "product"]
    ordering_fields = ["sort_order", "created_at"]
    ordering = ["product_group", "sort_order"]
