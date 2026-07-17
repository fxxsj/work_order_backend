from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from workorder import upload_paths


FIXED_NOW = datetime(2026, 7, 17, 1, 2, 3, 456789, tzinfo=timezone.utc)
FIXED_UUID_HEX = "1234567890abcdef1234567890abcdef"
FIXED_UUID_TOKEN = FIXED_UUID_HEX[:16]


@pytest.mark.parametrize(
    ("upload_to", "directory", "prefix"),
    [
        (upload_paths.artwork_image_upload_to, "artwork_images", "artwork"),
        (upload_paths.die_image_upload_to, "die_images", "die"),
        (
            upload_paths.foiling_plate_image_upload_to,
            "foiling_plate_images",
            "foiling_plate",
        ),
        (
            upload_paths.embossing_plate_image_upload_to,
            "embossing_plate_images",
            "embossing_plate",
        ),
        (upload_paths.product_image_upload_to, "product_images", "product"),
        (upload_paths.delivery_signature_upload_to, "signatures", "signature"),
        (upload_paths.work_order_design_upload_to, "designs", "design"),
        (upload_paths.invoice_attachment_upload_to, "invoices", "invoice"),
        (
            upload_paths.quality_report_upload_to,
            "quality_reports",
            "quality_report",
        ),
    ],
)
def test_module_upload_path_is_structured_and_does_not_keep_original_stem(
    upload_to,
    directory,
    prefix,
):
    with (
        patch("workorder.upload_paths.timezone.now", return_value=FIXED_NOW),
        patch("workorder.upload_paths.uuid.uuid4") as uuid4,
    ):
        uuid4.return_value.hex = FIXED_UUID_HEX

        path = upload_to(object(), "客户A../原始 文件.JPG")

    assert path == (
        f"{directory}/2026/07/"
        f"{prefix}_20260717T010203456789Z_{FIXED_UUID_TOKEN}.jpg"
    )
    assert "客户" not in path
    assert "原始" not in path


@pytest.mark.parametrize(
    ("filename", "expected_extension"),
    [
        ("scan.PNG", ".png"),
        ("archive.tar.GZ", ".gz"),
        ("no-extension", ".bin"),
        ("unsafe.toolongextension", ".bin"),
        ("unsafe.<svg", ".bin"),
    ],
)
def test_upload_path_only_keeps_a_short_alphanumeric_extension(
    filename,
    expected_extension,
):
    with (
        patch("workorder.upload_paths.timezone.now", return_value=FIXED_NOW),
        patch("workorder.upload_paths.uuid.uuid4") as uuid4,
    ):
        uuid4.return_value.hex = FIXED_UUID_HEX

        path = upload_paths.product_image_upload_to(object(), filename)

    assert path.endswith(expected_extension)


def test_upload_path_timestamp_is_normalized_to_utc():
    china_timezone = timezone(timedelta(hours=8))
    local_now = datetime(2026, 7, 17, 9, 2, 3, tzinfo=china_timezone)
    with (
        patch("workorder.upload_paths.timezone.now", return_value=local_now),
        patch("workorder.upload_paths.uuid.uuid4") as uuid4,
    ):
        uuid4.return_value.hex = FIXED_UUID_HEX

        path = upload_paths.product_image_upload_to(object(), "photo.jpg")

    assert "/2026/07/product_20260717T010203000000Z_" in path


def test_upload_paths_fit_django_file_field_default_max_length():
    upload_functions = [
        upload_paths.artwork_image_upload_to,
        upload_paths.die_image_upload_to,
        upload_paths.foiling_plate_image_upload_to,
        upload_paths.embossing_plate_image_upload_to,
        upload_paths.product_image_upload_to,
        upload_paths.delivery_signature_upload_to,
        upload_paths.work_order_design_upload_to,
        upload_paths.invoice_attachment_upload_to,
        upload_paths.quality_report_upload_to,
    ]

    paths = [function(object(), "file.abcdefghij") for function in upload_functions]

    assert all(len(path) <= 100 for path in paths)


def test_model_file_fields_use_module_specific_upload_paths():
    from workorder.models import (
        ArtworkImage,
        DeliveryOrder,
        DieImage,
        EmbossingPlateImage,
        FoilingPlateImage,
        Invoice,
        ProductImage,
        QualityInspection,
        WorkOrder,
    )

    field_paths = {
        ArtworkImage._meta.get_field(
            "image"
        ).upload_to: upload_paths.artwork_image_upload_to,
        DieImage._meta.get_field("image").upload_to: upload_paths.die_image_upload_to,
        FoilingPlateImage._meta.get_field(
            "image"
        ).upload_to: upload_paths.foiling_plate_image_upload_to,
        EmbossingPlateImage._meta.get_field(
            "image"
        ).upload_to: upload_paths.embossing_plate_image_upload_to,
        ProductImage._meta.get_field(
            "image"
        ).upload_to: upload_paths.product_image_upload_to,
        DeliveryOrder._meta.get_field(
            "receiver_signature"
        ).upload_to: upload_paths.delivery_signature_upload_to,
        WorkOrder._meta.get_field(
            "design_file"
        ).upload_to: upload_paths.work_order_design_upload_to,
        Invoice._meta.get_field(
            "attachment"
        ).upload_to: upload_paths.invoice_attachment_upload_to,
        QualityInspection._meta.get_field(
            "attachment"
        ).upload_to: upload_paths.quality_report_upload_to,
    }

    assert all(actual is expected for actual, expected in field_paths.items())
