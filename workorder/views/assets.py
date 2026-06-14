"""
资产相关视图集

包含图稿、刀模、烫金版、压凸版等资产的视图集。
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from workorder.response import APIResponse
from workorder.docs.assets import (
    artwork_create_version_docs,
    artwork_docs,
    artwork_product_docs,
    confirm_docs,
    die_docs,
    die_product_docs,
    embossing_plate_docs,
    embossing_product_docs,
    foiling_plate_docs,
    foiling_product_docs,
)

from ..models.assets import (
    Artwork,
    ArtworkImage,
    ArtworkProduct,
    Die,
    DieImage,
    DieProduct,
    EmbossingPlate,
    EmbossingPlateImage,
    EmbossingPlateProduct,
    FoilingPlate,
    FoilingPlateImage,
    FoilingPlateProduct,
)
from ..serializers.assets import (
    ArtworkImageSerializer,
    ArtworkProductSerializer,
    ArtworkSerializer,
    DieImageSerializer,
    DieProductSerializer,
    DieSerializer,
    EmbossingPlateImageSerializer,
    EmbossingPlateProductSerializer,
    EmbossingPlateSerializer,
    FoilingPlateImageSerializer,
    FoilingPlateProductSerializer,
    FoilingPlateSerializer,
)
from ..permissions import (
    SuperuserFriendlyModelPermissions,
    WorkOrderSupportingDataPermission,
)
from ..services.asset_service import (
    ArtworkVersionService,
    AssetConfirmationService,
    AssetImageService,
)
from ..services.service_errors import ServiceError
from .base_viewsets import BaseViewSet


class PlateMakingConfirmMixin:
    confirm_fk_field: str = ""
    confirm_error_message: str = "该资产已经确认过了"

    def _confirm_select_for_update(self, pk):
        return self.get_queryset().select_for_update().get(pk=pk)

    @action(detail=True, methods=["post"])
    @confirm_docs
    def confirm(self, request, pk=None):
        """设计部确认资产，并尝试完成对应制版任务"""
        asset = self.get_object()

        try:
            AssetConfirmationService.confirm(
                asset=asset,
                fk_field=self.confirm_fk_field,
                user=request.user,
            )
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code, data=e.data)

        serializer = self.get_serializer(asset)
        return APIResponse.success(data=serializer.data)


class ImageAssetActionsMixin:
    image_model = None
    image_serializer_class = None
    image_parent_field = ""

    def _get_image_config(self):
        if (
            self.image_model is None
            or self.image_serializer_class is None
            or not self.image_parent_field
        ):
            raise RuntimeError("图片上传配置不完整")
        return self.image_model, self.image_serializer_class, self.image_parent_field

    @action(detail=True, methods=["get"])
    def images(self, request, pk=None):
        """获取资产的所有图片，按排序返回"""
        _, serializer_class, _ = self._get_image_config()
        asset = self.get_object()
        images = AssetImageService.list_images(asset)
        serializer = serializer_class(images, many=True)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    def upload_image(self, request, pk=None):
        """上传图片到指定资产"""
        image_model, serializer_class, parent_field = self._get_image_config()
        asset = self.get_object()
        image_file = request.FILES.get("image")
        if not image_file:
            return APIResponse.error(
                "请选择要上传的图片",
                code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            image = AssetImageService.create_image(
                image_model=image_model,
                parent_field=parent_field,
                asset=asset,
                image_file=image_file,
                sort_order=int(request.POST.get("sort_order", 0)),
                description=request.POST.get("description", "").strip(),
            )
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code, data=e.data)

        serializer = serializer_class(image)
        return APIResponse.success(
            data=serializer.data,
            code=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(self, request, pk=None, image_id=None):
        """删除资产的指定图片"""
        image_model, _, parent_field = self._get_image_config()
        try:
            AssetImageService.delete_image(
                image_model=image_model,
                parent_field=parent_field,
                asset_pk=pk,
                image_id=image_id,
            )
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code, data=e.data)
        return APIResponse.success(message="图片已删除")


@artwork_docs
class ArtworkViewSet(PlateMakingConfirmMixin, ImageAssetActionsMixin, BaseViewSet):
    """图稿视图集"""

    confirm_fk_field = "artwork"
    confirm_error_message = "该图稿已经确认过了"
    image_model = ArtworkImage
    image_serializer_class = ArtworkImageSerializer
    image_parent_field = "artwork"

    queryset = Artwork.objects.all()
    serializer_class = ArtworkSerializer
    permission_classes = [WorkOrderSupportingDataPermission]
    filterset_fields = ["base_code", "version", "confirmed", "products__product"]
    search_fields = ["base_code", "name", "imposition_size", "notes"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "base_code",
        "version",
        "name",
        "imposition_size",
        "confirmed",
        "confirmed_at",
    ]
    ordering = ["-base_code", "-version"]

    @action(detail=True, methods=["post"])
    @artwork_create_version_docs
    def create_version(self, request, pk=None):
        """基于现有图稿创建新版本

        复制原图稿的所有信息，包括：
        - 基本信息（名称、颜色、尺寸、备注）
        - 关联刀模
        - 关联烫金版
        - 关联压凸版
        - 关联产品及拼版数量
        """
        original_artwork = self.get_object()

        try:
            new_artwork = ArtworkVersionService.create_version(original_artwork)
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code, data=e.data)

        serializer = self.get_serializer(new_artwork)
        return APIResponse.success(data=serializer.data, code=status.HTTP_201_CREATED)

    def get_queryset(self):
        """优化查询性能：预加载关联数据"""
        queryset = super().get_queryset()
        return queryset.prefetch_related(
            "products__product", "dies", "foiling_plates", "embossing_plates", "images"
        ).select_related("confirmed_by")


@die_docs
class DieViewSet(PlateMakingConfirmMixin, ImageAssetActionsMixin, BaseViewSet):
    """刀模视图集"""

    confirm_fk_field = "die"
    confirm_error_message = "该刀模已经确认过了"
    image_model = DieImage
    image_serializer_class = DieImageSerializer
    image_parent_field = "die"

    queryset = Die.objects.all()
    serializer_class = DieSerializer
    permission_classes = [WorkOrderSupportingDataPermission]
    filterset_fields = ["confirmed", "die_type", "products__product"]
    search_fields = ["code", "name", "size", "material"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "code",
        "name",
        "die_type",
        "size",
        "material",
        "thickness",
        "confirmed",
        "confirmed_at",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        """优化查询性能：预加载关联数据"""
        queryset = super().get_queryset()
        return queryset.prefetch_related("products__product", "images").select_related(
            "confirmed_by"
        )


@foiling_plate_docs
class FoilingPlateViewSet(
    PlateMakingConfirmMixin,
    ImageAssetActionsMixin,
    BaseViewSet,
):
    """烫金版视图集"""

    confirm_fk_field = "foiling_plate"
    confirm_error_message = "该烫金版已经确认过了"
    image_model = FoilingPlateImage
    image_serializer_class = FoilingPlateImageSerializer
    image_parent_field = "foiling_plate"

    queryset = FoilingPlate.objects.all()
    serializer_class = FoilingPlateSerializer
    permission_classes = [WorkOrderSupportingDataPermission]
    filterset_fields = ["confirmed", "foiling_type", "products__product"]
    search_fields = ["code", "name", "size", "material"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "code",
        "name",
        "foiling_type",
        "size",
        "material",
        "thickness",
        "confirmed",
        "confirmed_at",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        """优化查询性能：预加载关联数据"""
        queryset = super().get_queryset()
        return queryset.prefetch_related("products__product", "images").select_related(
            "confirmed_by"
        )


@embossing_plate_docs
class EmbossingPlateViewSet(
    PlateMakingConfirmMixin,
    ImageAssetActionsMixin,
    BaseViewSet,
):
    """压凸版视图集"""

    confirm_fk_field = "embossing_plate"
    confirm_error_message = "该压凸版已经确认过了"
    image_model = EmbossingPlateImage
    image_serializer_class = EmbossingPlateImageSerializer
    image_parent_field = "embossing_plate"

    queryset = EmbossingPlate.objects.all()
    serializer_class = EmbossingPlateSerializer
    permission_classes = [WorkOrderSupportingDataPermission]
    filterset_fields = ["confirmed", "products__product"]
    search_fields = ["code", "name", "size", "material"]
    ordering_fields = ["created_at", "code", "name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """优化查询性能：预加载关联数据"""
        queryset = super().get_queryset()
        return queryset.prefetch_related("products__product", "images").select_related(
            "confirmed_by"
        )


@artwork_product_docs
class _ProductRelationViewSet(viewsets.ModelViewSet):
    """Base ViewSet for plate/artwork product relations.

    Subclasses must set:
        queryset, serializer_class, product_relation_field
    """

    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ["sort_order"]
    product_relation_field: str = ""

    def get_filterset(self):
        from django_filters import FilterSet

        class AutoFilterSet(FilterSet):
            class Meta:
                model = self.queryset.model
                fields = [self.product_relation_field, "product"]

        return AutoFilterSet

    @property
    def ordering(self):
        return [self.product_relation_field, "sort_order"]


class ArtworkProductViewSet(_ProductRelationViewSet):
    """图稿产品视图集"""

    queryset = ArtworkProduct.objects.all()
    serializer_class = ArtworkProductSerializer
    product_relation_field = "artwork"


@die_product_docs
class DieProductViewSet(_ProductRelationViewSet):
    """刀模产品视图集"""

    queryset = DieProduct.objects.all()
    serializer_class = DieProductSerializer
    product_relation_field = "die"


@foiling_product_docs
class FoilingPlateProductViewSet(_ProductRelationViewSet):
    """烫金版产品视图集"""

    queryset = FoilingPlateProduct.objects.all()
    serializer_class = FoilingPlateProductSerializer
    product_relation_field = "foiling_plate"


@embossing_product_docs
class EmbossingPlateProductViewSet(_ProductRelationViewSet):
    """压凸版产品视图集"""

    queryset = EmbossingPlateProduct.objects.all()
    serializer_class = EmbossingPlateProductSerializer
    product_relation_field = "embossing_plate"
