"""
资产相关视图集

包含图稿、刀模、烫金版、压凸版等资产的视图集。
"""

from pathlib import Path

from django.db.models import Sum
from django.utils import timezone
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
from ..models.core import WorkOrder, WorkOrderProcess, WorkOrderTask
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
        from django.db import transaction

        if not self.confirm_fk_field:
            return APIResponse.error(
                "未配置 confirm_fk_field", code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        with transaction.atomic():
            asset = self._confirm_select_for_update(pk)

            if asset.confirmed:
                return APIResponse.error(
                    self.confirm_error_message, code=status.HTTP_400_BAD_REQUEST
                )

            asset.confirmed = True
            asset.confirmed_by = request.user
            asset.confirmed_at = timezone.now()
            asset.save()

            tasks = WorkOrderTask.objects.filter(
                **{self.confirm_fk_field: asset},
                task_type="plate_making",
                work_order_process__status="in_progress",
            )

            for task in tasks:
                related = getattr(task, self.confirm_fk_field, None)
                if related and related.confirmed:
                    task.status = "completed"
                    task.quantity_completed = 1
                    task.save()
                    task.work_order_process.check_and_update_status()

        serializer = self.get_serializer(asset)
        return APIResponse.success(data=serializer.data)


class ImageAssetActionsMixin:
    allowed_image_extensions = {"jpg", "jpeg", "png", "webp", "gif"}
    max_image_size_bytes = 10 * 1024 * 1024
    max_image_count = 12
    image_model = None
    image_serializer_class = None
    image_parent_field = ""
    image_missing_message = "图片不存在"
    image_select_message = "请选择要上传的图片"
    image_type_message = "仅支持 JPG、PNG、WebP、GIF 图片"
    image_size_message = "图片不能超过 10MB"
    image_count_message = "图片最多上传 12 张"

    def _get_image_config(self):
        if (
            self.image_model is None
            or self.image_serializer_class is None
            or not self.image_parent_field
        ):
            raise RuntimeError("图片上传配置不完整")
        return self.image_model, self.image_serializer_class, self.image_parent_field

    def _validate_upload_image(self, asset, image_file):
        if asset.images.count() >= self.max_image_count:
            return APIResponse.error(
                self.image_count_message,
                code=status.HTTP_400_BAD_REQUEST,
            )

        suffix = Path(getattr(image_file, "name", "")).suffix.lower().lstrip(".")
        if suffix not in self.allowed_image_extensions:
            return APIResponse.error(
                self.image_type_message,
                code=status.HTTP_400_BAD_REQUEST,
            )

        if getattr(image_file, "size", 0) > self.max_image_size_bytes:
            return APIResponse.error(
                self.image_size_message,
                code=status.HTTP_400_BAD_REQUEST,
            )

        return None

    @action(detail=True, methods=["get"])
    def images(self, request, pk=None):
        """获取资产的所有图片，按排序返回"""
        _, serializer_class, _ = self._get_image_config()
        asset = self.get_object()
        images = asset.images.all().order_by("sort_order")
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
                self.image_select_message,
                code=status.HTTP_400_BAD_REQUEST,
            )
        validation_error = self._validate_upload_image(asset, image_file)
        if validation_error is not None:
            return validation_error

        sort_order = int(request.POST.get("sort_order", 0))
        description = request.POST.get("description", "").strip()
        image = image_model.objects.create(
            **{
                parent_field: asset,
                "image": image_file,
                "sort_order": sort_order,
                "description": description,
            }
        )
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
            image = image_model.objects.get(
                pk=image_id,
                **{f"{parent_field}_id": pk},
            )
            image.image.delete(save=False)
            image.delete()
            return APIResponse.success(message="图片已删除")
        except image_model.DoesNotExist:
            return APIResponse.error(
                self.image_missing_message,
                code=status.HTTP_404_NOT_FOUND,
            )


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
    filterset_fields = ["base_code", "version", "confirmed"]
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
        from django.db import transaction

        original_artwork = self.get_object()

        with transaction.atomic():
            # 获取下一个版本号
            next_version = Artwork.get_next_version(original_artwork.base_code)

            # 创建新版本，复制原图稿的所有信息
            new_artwork = Artwork.objects.create(
                base_code=original_artwork.base_code,
                version=next_version,
                name=original_artwork.name,
                cmyk_colors=(
                    original_artwork.cmyk_colors.copy()
                    if original_artwork.cmyk_colors
                    else []
                ),
                other_colors=(
                    original_artwork.other_colors.copy()
                    if original_artwork.other_colors
                    else []
                ),
                imposition_size=original_artwork.imposition_size,
                notes=original_artwork.notes,
            )

            # 复制关联的刀模
            new_artwork.dies.set(original_artwork.dies.all())

            # 复制关联的烫金版
            new_artwork.foiling_plates.set(original_artwork.foiling_plates.all())

            # 复制关联的压凸版
            new_artwork.embossing_plates.set(original_artwork.embossing_plates.all())

            # 复制关联的产品
            for ap in original_artwork.products.all():
                ArtworkProduct.objects.create(
                    artwork=new_artwork,
                    product=ap.product,
                    imposition_quantity=ap.imposition_quantity,
                    sort_order=ap.sort_order,
                )

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
    filterset_fields = ["confirmed", "die_type"]
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
    filterset_fields = ["confirmed", "foiling_type"]
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
    filterset_fields = []
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
