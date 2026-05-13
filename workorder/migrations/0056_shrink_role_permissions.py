"""
角色权限矩阵精简 - 业务减法

1. admin 移除 delete_customer（delete 权限只给超级管理员）
2. sales 移除 change_workorder（只能创建和查看自己的施工单）
"""

from django.db import migrations

from workorder.permissions.role_matrix import (
    ROLE_ALIASES,
    ROLE_CUSTOM_PERMISSIONS,
    ROLE_PERMISSIONS,
    STALE_PERMISSION_MODELS,
)


def normalize_role_groups_v2(apps, schema_editor):
    """应用精简后的角色权限矩阵"""
    from django.contrib.auth.management import create_permissions
    from django.apps import apps as global_apps

    app_config = global_apps.get_app_config("workorder")
    create_permissions(
        app_config,
        verbosity=0,
        using=schema_editor.connection.alias,
        apps=apps,
    )

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    def get_model(model_name):
        try:
            return apps.get_model("workorder", model_name)
        except LookupError:
            return None

    def get_default_perm(action, model_name):
        model = get_model(model_name)
        if model is None:
            return None
        try:
            content_type = ContentType.objects.get_for_model(model)
        except ContentType.DoesNotExist:
            return None
        codename = f"{action}_{model._meta.model_name}"
        return Permission.objects.filter(
            content_type=content_type,
            codename=codename,
        ).first()

    def get_custom_perm(codename, model_name):
        model = get_model(model_name)
        if model is None:
            return None
        try:
            content_type = ContentType.objects.get_for_model(model)
        except ContentType.DoesNotExist:
            return None
        return Permission.objects.filter(
            content_type=content_type,
            codename=codename,
        ).first()

    for role_name, model_actions in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=role_name)
        group.permissions.clear()
        for model_name, actions in model_actions.items():
            for action in actions:
                permission = get_default_perm(action, model_name)
                if permission:
                    group.permissions.add(permission)
        for model_name, codenames in ROLE_CUSTOM_PERMISSIONS.get(role_name, {}).items():
            for codename in codenames:
                permission = get_custom_perm(codename, model_name)
                if permission:
                    group.permissions.add(permission)

    for alias_name, target_name in ROLE_ALIASES.items():
        alias_group = Group.objects.filter(name=alias_name).first()
        target_group = Group.objects.filter(name=target_name).first()
        if not alias_group or not target_group:
            continue
        for user in alias_group.user_set.all():
            target_group.user_set.add(user)
        alias_group.delete()

    stale_content_types = ContentType.objects.filter(
        app_label="workorder",
        model__in=STALE_PERMISSION_MODELS,
    )
    Permission.objects.filter(content_type__in=stale_content_types).delete()
    stale_content_types.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("workorder", "0055_normalize_role_groups"),
    ]

    operations = [
        migrations.RunPython(
            normalize_role_groups_v2,
            migrations.RunPython.noop,
        ),
    ]
