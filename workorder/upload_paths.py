"""Stable, privacy-safe object keys for uploaded files."""

import re
import uuid
from datetime import timezone as datetime_timezone
from pathlib import PurePath

from django.utils import timezone


_SAFE_EXTENSION = re.compile(r"^\.[a-z0-9]{1,10}$")


def _normalized_extension(filename: str) -> str:
    extension = PurePath(filename or "").suffix.lower()
    if _SAFE_EXTENSION.fullmatch(extension):
        return extension
    return ".bin"


def _build_upload_path(directory: str, prefix: str, filename: str) -> str:
    uploaded_at = timezone.now()
    if timezone.is_naive(uploaded_at):
        uploaded_at = timezone.make_aware(uploaded_at, datetime_timezone.utc)
    uploaded_at = uploaded_at.astimezone(datetime_timezone.utc)
    timestamp = uploaded_at.strftime("%Y%m%dT%H%M%S%fZ")
    unique_id = uuid.uuid4().hex[:16]
    extension = _normalized_extension(filename)
    return (
        f"{directory}/{uploaded_at:%Y/%m}/"
        f"{prefix}_{timestamp}_{unique_id}{extension}"
    )


def artwork_image_upload_to(instance, filename: str) -> str:
    return _build_upload_path("artwork_images", "artwork", filename)


def die_image_upload_to(instance, filename: str) -> str:
    return _build_upload_path("die_images", "die", filename)


def foiling_plate_image_upload_to(instance, filename: str) -> str:
    return _build_upload_path("foiling_plate_images", "foiling_plate", filename)


def embossing_plate_image_upload_to(instance, filename: str) -> str:
    return _build_upload_path("embossing_plate_images", "embossing_plate", filename)


def product_image_upload_to(instance, filename: str) -> str:
    return _build_upload_path("product_images", "product", filename)


def delivery_signature_upload_to(instance, filename: str) -> str:
    return _build_upload_path("signatures", "signature", filename)


def work_order_design_upload_to(instance, filename: str) -> str:
    return _build_upload_path("designs", "design", filename)


def invoice_attachment_upload_to(instance, filename: str) -> str:
    return _build_upload_path("invoices", "invoice", filename)


def quality_report_upload_to(instance, filename: str) -> str:
    return _build_upload_path("quality_reports", "quality_report", filename)
