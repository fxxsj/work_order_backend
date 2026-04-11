"""
资产相关视图集

包含图稿、刀模、烫金版、压凸版等资产的视图集。
"""

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
from ..permissions import WorkOrderSupportingDataPermission
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
            return APIResponse.error("未配置 confirm_fk_field", code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        with transaction.atomic():
            asset = self._confirm_select_for_update(pk)

            if asset.confirmed:
                return APIResponse.error(self.confirm_error_message, code=status.HTTP_400_BAD_REQUEST)

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


@artwork_docs
class ArtworkViewSet(PlateMakingConfirmMixin, BaseViewSet):
    """图稿视图集"""

    confirm_fk_field = "artwork"
    confirm_error_message = "该图稿已经确认过了"

    queryset = Artwork.objects.all()
    serializer_class = ArtworkSerializer
    permission_classes = [WorkOrderSupportingDataPermission]
    filterset_fields = ["base_code", "version"]
    search_fields = ["base_code", "name", "imposition_size"]
    ordering_fields = ["created_at", "base_code", "version", "name"]
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

    @action(detail=True, methods=["get"])
    def images(self, request, pk=None):
        """获取图稿的所有图片，按排序返回"""
        artwork = self.get_object()
        images = artwork.images.all().order_by("sort_order")
        serializer = ArtworkImageSerializer(images, many=True)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    def upload_image(self, request, pk=None):
        """上传图片到指定图稿"""
        artwork = self.get_object()
        image_file = request.FILES.get("image")
        if not image_file:
            return APIResponse.error("请选择要上传的图片", code=status.HTTP_400_BAD_REQUEST)

        sort_order = int(request.POST.get("sort_order", 0))
        description = request.POST.get("description", "").strip()

        img = ArtworkImage.objects.create(
            artwork=artwork,
            image=image_file,
            sort_order=sort_order,
            description=description,
        )
        serializer = ArtworkImageSerializer(img)
        return APIResponse.success(data=serializer.data, code=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(self, request, pk=None, image_id=None):
        """删除图稿的指定图片"""
        try:
            img = ArtworkImage.objects.get(pk=image_id, artwork_id=pk)
            img.image.delete(save=False)  # 删除物理文件
            img.delete()
            return APIResponse.success(message="图片已删除")
        except ArtworkImage.DoesNotExist:
            return APIResponse.error("图片不存在", code=status.HTTP_404_NOT_FOUND)

    def get_queryset(self):
        """优化查询性能：预加载关联数据"""
        queryset = super().get_queryset()
        return queryset.prefetch_related(
            "products__product", "dies", "foiling_plates", "embossing_plates", "images"
        ).select_related("confirmed_by")


@die_docs
class DieViewSet(PlateMakingConfirmMixin, BaseViewSet):
    """刀模视图集"""

    confirm_fk_field = "die"
    confirm_error_message = "该刀模已经确认过了"

    queryset = Die.objects.all()
    serializer_class = DieSerializer
    permission_classes = [WorkOrderSupportingDataPermission]
    filterset_fields = ["confirmed"]
    search_fields = ["code", "name", "size", "material"]
    ordering_fields = ["created_at", "code", "name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """优化查询性能：预加载关联数据"""
        queryset = super().get_queryset()
        return queryset.prefetch_related("products__product", "images").select_related(
            "confirmed_by"
        )

    @action(detail=True, methods=["get"])
    def images(self, request, pk=None):
        """获取刀模的所有图片，按排序返回"""
        die = self.get_object()
        images = die.images.all().order_by("sort_order")
        serializer = DieImageSerializer(images, many=True)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    def upload_image(self, request, pk=None):
        """上传图片到指定刀模"""
        die = self.get_object()
        image_file = request.FILES.get("image")
        if not image_file:
            return APIResponse.error("请选择要上传的图片", code=status.HTTP_400_BAD_REQUEST)

        sort_order = int(request.POST.get("sort_order", 0))
        description = request.POST.get("description", "").strip()

        img = DieImage.objects.create(
            die=die,
            image=image_file,
            sort_order=sort_order,
            description=description,
        )
        serializer = DieImageSerializer(img)
        return APIResponse.success(data=serializer.data, code=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(self, request, pk=None, image_id=None):
        """删除刀模的指定图片"""
        try:
            img = DieImage.objects.get(pk=image_id, die_id=pk)
            img.image.delete(save=False)  # 删除物理文件
            img.delete()
            return APIResponse.success(message="图片已删除")
        except DieImage.DoesNotExist:
            return APIResponse.error("图片不存在", code=status.HTTP_404_NOT_FOUND)


@foiling_plate_docs
class FoilingPlateViewSet(PlateMakingConfirmMixin, BaseViewSet):
    """烫金版视图集"""

    confirm_fk_field = "foiling_plate"
    confirm_error_message = "该烫金版已经确认过了"

    queryset = FoilingPlate.objects.all()
    serializer_class = FoilingPlateSerializer
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

    @action(detail=True, methods=["get"])
    def images(self, request, pk=None):
        """获取烫金版的所有图片，按排序返回"""
        plate = self.get_object()
        images = plate.images.all().order_by("sort_order")
        serializer = FoilingPlateImageSerializer(images, many=True)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    def upload_image(self, request, pk=None):
        """上传图片到指定烫金版"""
        plate = self.get_object()
        image_file = request.FILES.get("image")
        if not image_file:
            return APIResponse.error("请选择要上传的图片", code=status.HTTP_400_BAD_REQUEST)

        sort_order = int(request.POST.get("sort_order", 0))
        description = request.POST.get("description", "").strip()

        img = FoilingPlateImage.objects.create(
            foiling_plate=plate,
            image=image_file,
            sort_order=sort_order,
            description=description,
        )
        serializer = FoilingPlateImageSerializer(img)
        return APIResponse.success(data=serializer.data, code=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(self, request, pk=None, image_id=None):
        """删除烫金版的指定图片"""
        try:
            img = FoilingPlateImage.objects.get(pk=image_id, foiling_plate_id=pk)
            img.image.delete(save=False)  # 删除物理文件
            img.delete()
            return APIResponse.success(message="图片已删除")
        except FoilingPlateImage.DoesNotExist:
            return APIResponse.error("图片不存在", code=status.HTTP_404_NOT_FOUND)


@embossing_plate_docs
class EmbossingPlateViewSet(PlateMakingConfirmMixin, BaseViewSet):
    """压凸版视图集"""

    confirm_fk_field = "embossing_plate"
    confirm_error_message = "该压凸版已经确认过了"

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

    @action(detail=True, methods=["get"])
    def images(self, request, pk=None):
        """获取压凸版的所有图片，按排序返回"""
        plate = self.get_object()
        images = plate.images.all().order_by("sort_order")
        serializer = EmbossingPlateImageSerializer(images, many=True)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    def upload_image(self, request, pk=None):
        """上传图片到指定压凸版"""
        plate = self.get_object()
        image_file = request.FILES.get("image")
        if not image_file:
            return APIResponse.error("请选择要上传的图片", code=status.HTTP_400_BAD_REQUEST)

        sort_order = int(request.POST.get("sort_order", 0))
        description = request.POST.get("description", "").strip()

        img = EmbossingPlateImage.objects.create(
            embossing_plate=plate,
            image=image_file,
            sort_order=sort_order,
            description=description,
        )
        serializer = EmbossingPlateImageSerializer(img)
        return APIResponse.success(data=serializer.data, code=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(self, request, pk=None, image_id=None):
        """删除压凸版的指定图片"""
        try:
            img = EmbossingPlateImage.objects.get(pk=image_id, embossing_plate_id=pk)
            img.image.delete(save=False)  # 删除物理文件
            img.delete()
            return APIResponse.success(message="图片已删除")
        except EmbossingPlateImage.DoesNotExist:
            return APIResponse.error("图片不存在", code=status.HTTP_404_NOT_FOUND)


@artwork_product_docs
class ArtworkProductViewSet(viewsets.ModelViewSet):
    """图稿产品视图集"""

    queryset = ArtworkProduct.objects.all()
    serializer_class = ArtworkProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ["sort_order"]
    ordering = ["artwork", "sort_order"]

    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class ArtworkProductFilterSet(FilterSet):
            class Meta:
                model = ArtworkProduct
                fields = ["artwork", "product"]

        return ArtworkProductFilterSet


@die_product_docs
class DieProductViewSet(viewsets.ModelViewSet):
    """刀模产品视图集"""

    queryset = DieProduct.objects.all()
    serializer_class = DieProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ["sort_order"]
    ordering = ["die", "sort_order"]

    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class DieProductFilterSet(FilterSet):
            class Meta:
                model = DieProduct
                fields = ["die", "product"]

        return DieProductFilterSet


@foiling_product_docs
class FoilingPlateProductViewSet(viewsets.ModelViewSet):
    """烫金版产品视图集"""

    queryset = FoilingPlateProduct.objects.all()
    serializer_class = FoilingPlateProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ["sort_order"]
    ordering = ["foiling_plate", "sort_order"]

    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class FoilingPlateProductFilterSet(FilterSet):
            class Meta:
                model = FoilingPlateProduct
                fields = ["foiling_plate", "product"]

        return FoilingPlateProductFilterSet


@embossing_product_docs
class EmbossingPlateProductViewSet(viewsets.ModelViewSet):
    """压凸版产品视图集"""

    queryset = EmbossingPlateProduct.objects.all()
    serializer_class = EmbossingPlateProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ["sort_order"]
    ordering = ["embossing_plate", "sort_order"]

    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class EmbossingPlateProductFilterSet(FilterSet):
            class Meta:
                model = EmbossingPlateProduct
                fields = ["embossing_plate", "product"]

        return EmbossingPlateProductFilterSet
