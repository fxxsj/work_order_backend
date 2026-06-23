from django.apps import apps
from django.contrib import admin
from django.contrib.admin.utils import flatten_fieldsets
import pytest


INLINE_ONLY_MODELS = {
    "ArtworkImage",
    "ArtworkProduct",
    "DieImage",
    "DieProduct",
    "EmbossingPlateImage",
    "EmbossingPlateProduct",
    "FoilingPlateImage",
    "FoilingPlateProduct",
    "ProductImage",
    "ProductMaterial",
    "WorkOrderProduct",
}

EXPECTED_ADMIN_GROUPS = {
    "基础资料",
    "产品与资产",
    "销售与生产",
    "采购与库存",
    "财务管理",
    "系统与审计",
}


def _get_field(model, field_name):
    try:
        return model._meta.get_field(field_name)
    except Exception:
        return None


def _field_path_exists(model, field_path):
    current_model = model
    for part in field_path.split("__"):
        field = _get_field(current_model, part)
        if field is None:
            return False
        if field.is_relation and field.related_model:
            current_model = field.related_model
    return True


def _relation_path_exists(model, field_path):
    current_model = model
    for part in field_path.split("__"):
        field = _get_field(current_model, part)
        if field is None or not field.is_relation or not field.related_model:
            return False
        current_model = field.related_model
    return True


def _admin_or_model_attr_exists(model_admin, model, name):
    if hasattr(model_admin, name) or hasattr(model, name):
        return True
    if name.startswith("get_") and name.endswith("_display"):
        field_name = name[4:-8]
        return _get_field(model, field_name) is not None
    return _get_field(model, name) is not None


def test_all_non_inline_workorder_models_are_registered_in_admin():
    registered_models = {
        model.__name__
        for model in admin.site._registry
        if model._meta.app_label == "workorder"
    }
    all_models = {
        model.__name__
        for model in apps.get_app_config("workorder").get_models()
    }

    assert sorted((all_models - registered_models) - INLINE_ONLY_MODELS) == []


def test_workorder_admin_field_references_are_valid():
    invalid_refs = []

    for model, model_admin in admin.site._registry.items():
        if model._meta.app_label != "workorder":
            continue

        fieldsets = getattr(model_admin, "fieldsets", None)
        if fieldsets:
            for field_name in flatten_fieldsets(fieldsets):
                if not _admin_or_model_attr_exists(
                    model_admin, model, field_name
                ):
                    invalid_refs.append(
                        (model.__name__, "fieldsets", field_name)
                    )

        for field_name in getattr(model_admin, "autocomplete_fields", []):
            if not _relation_path_exists(model, field_name):
                invalid_refs.append(
                    (model.__name__, "autocomplete_fields", field_name)
                )

        for field_path in (
            getattr(model_admin, "list_select_related", []) or []
        ):
            if not _relation_path_exists(model, field_path):
                invalid_refs.append(
                    (model.__name__, "list_select_related", field_path)
                )

        for field_path in getattr(model_admin, "search_fields", []):
            normalized = field_path.lstrip("^=@")
            if not _field_path_exists(model, normalized):
                invalid_refs.append(
                    (model.__name__, "search_fields", field_path)
                )

        for item in getattr(model_admin, "list_display", []):
            if isinstance(item, str) and not _admin_or_model_attr_exists(
                model_admin, model, item
            ):
                invalid_refs.append((model.__name__, "list_display", item))

        for item in getattr(model_admin, "list_filter", []):
            if isinstance(item, str) and not _field_path_exists(model, item):
                invalid_refs.append((model.__name__, "list_filter", item))

    assert invalid_refs == []


@pytest.mark.django_db
def test_workorder_admin_index_is_grouped_by_business_domain(rf):
    request = rf.get("/admin/")
    request.user = type(
        "AdminUser",
        (),
        {
            "is_active": True,
            "is_staff": True,
            "has_module_perms": lambda self, app_label: True,
            "has_perm": lambda self, perm: True,
        },
    )()

    group_names = {
        app["name"]
        for app in admin.site.get_app_list(request)
        if app["app_label"].startswith("workorder")
    }

    assert EXPECTED_ADMIN_GROUPS <= group_names
