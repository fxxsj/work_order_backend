"""
资产相关业务服务

将 assets.py 中的确认、图片管理和版本创建逻辑下沉到服务层，
保持视图集（和 mixin）只负责路由、序列化和响应包装。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone
from rest_framework import status

from ..models.assets import Artwork, ArtworkProduct
from ..models.core import WorkOrderTask
from .service_errors import ServiceError

logger = logging.getLogger(__name__)


class AssetConfirmationService:
    """资产确认服务（图稿、刀模、烫金版、压凸版）。"""

    @staticmethod
    def confirm(asset, fk_field: str, user) -> Any:
        """确认资产，并尝试完成对应制版任务。

        Args:
            asset: 资产实例（Artwork / Die / FoilingPlate / EmbossingPlate）
            fk_field: 任务上指向该资产的外键字段名
            user: 当前用户

        Returns:
            确认后的资产实例
        """
        if not fk_field:
            raise ServiceError(
                "未配置 confirm_fk_field",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        with transaction.atomic():
            if asset.confirmed:
                raise ServiceError(
                    "该资产已经确认过了",
                    code=status.HTTP_400_BAD_REQUEST,
                )

            asset.confirmed = True
            asset.confirmed_by = user
            asset.confirmed_at = timezone.now()
            asset.save()

            tasks = WorkOrderTask.objects.filter(
                **{fk_field: asset},
                task_type="plate_making",
                work_order_process__status="in_progress",
            )

            for task in tasks:
                related = getattr(task, fk_field, None)
                if related and related.confirmed:
                    task.status = "completed"
                    task.quantity_completed = 1
                    task.save()
                    task.work_order_process.check_and_update_status()

        return asset


class AssetImageService:
    """资产图片上传/删除/查询服务。"""

    allowed_image_extensions = {"jpg", "jpeg", "png", "webp", "gif"}
    max_image_size_bytes = 10 * 1024 * 1024
    max_image_count = 12

    @staticmethod
    def list_images(asset) -> Any:
        """返回资产下按排序号的图片查询集。"""
        return asset.images.all().order_by("sort_order")

    @staticmethod
    def create_image(
        image_model,
        parent_field: str,
        asset,
        image_file,
        sort_order: int = 0,
        description: str = "",
    ) -> Any:
        """验证并创建资产图片。

        Raises:
            ServiceError: 校验失败时
        """
        if asset.images.count() >= AssetImageService.max_image_count:
            raise ServiceError(
                "图片最多上传 12 张",
                code=status.HTTP_400_BAD_REQUEST,
            )

        suffix = Path(getattr(image_file, "name", "")).suffix.lower().lstrip(".")
        if suffix not in AssetImageService.allowed_image_extensions:
            raise ServiceError(
                "仅支持 JPG、PNG、WebP、GIF 图片",
                code=status.HTTP_400_BAD_REQUEST,
            )

        if getattr(image_file, "size", 0) > AssetImageService.max_image_size_bytes:
            raise ServiceError(
                "图片不能超过 10MB",
                code=status.HTTP_400_BAD_REQUEST,
            )

        return image_model.objects.create(
            **{
                parent_field: asset,
                "image": image_file,
                "sort_order": sort_order,
                "description": description,
            }
        )

    @staticmethod
    def delete_image(image_model, parent_field: str, asset_pk, image_id) -> None:
        """删除资产下的指定图片。

        Raises:
            ServiceError: 图片不存在时返回 404
        """
        try:
            image = image_model.objects.get(
                pk=image_id,
                **{f"{parent_field}_id": asset_pk},
            )
        except image_model.DoesNotExist as exc:
            raise ServiceError(
                "图片不存在",
                code=status.HTTP_404_NOT_FOUND,
            ) from exc

        image.image.delete(save=False)
        image.delete()


class ArtworkVersionService:
    """图稿版本创建服务。"""

    @staticmethod
    def create_version(original_artwork: Artwork) -> Artwork:
        """基于现有图稿创建新版本，复制关联关系。"""
        with transaction.atomic():
            next_version = Artwork.get_next_version(original_artwork.base_code)

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

            new_artwork.dies.set(original_artwork.dies.all())
            new_artwork.foiling_plates.set(original_artwork.foiling_plates.all())
            new_artwork.embossing_plates.set(original_artwork.embossing_plates.all())

            for ap in original_artwork.products.all():
                ArtworkProduct.objects.create(
                    artwork=new_artwork,
                    product=ap.product,
                    imposition_quantity=ap.imposition_quantity,
                    sort_order=ap.sort_order,
                )

        return new_artwork
