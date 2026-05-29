from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

from workorder.permissions.role_matrix import (
    ROLE_ALIASES,
    ROLE_CUSTOM_PERMISSIONS,
    ROLE_PERMISSIONS,
)


def sync_role_permissions(apps, schema_editor):
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
        content_type = ContentType.objects.get_for_model(model)
        return Permission.objects.filter(
            content_type=content_type,
            codename=f"{action}_{model._meta.model_name}",
        ).first()

    def get_custom_perm(codename, model_name):
        model = get_model(model_name)
        if model is None:
            return None
        content_type = ContentType.objects.get_for_model(model)
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


def align_department_presets(apps, schema_editor):
    Department = apps.get_model("workorder", "Department")
    Process = apps.get_model("workorder", "Process")
    TaskAssignmentRule = apps.get_model("workorder", "TaskAssignmentRule")

    Department.objects.update_or_create(
        code="quality",
        defaults={
            "name": "质检部",
            "sort_order": 11,
            "is_active": True,
            "parent": None,
        },
    )
    Department.objects.filter(code="logistics").update(sort_order=12)

    design_department = Department.objects.filter(code="design").first()
    ctp_process = Process.objects.filter(code="CTP").first()
    if design_department and ctp_process:
        design_department.processes.add(ctp_process)
        TaskAssignmentRule.objects.update_or_create(
            process=ctp_process,
            department=design_department,
            defaults={
                "priority": 100,
                "operator_selection_strategy": "least_tasks",
                "is_active": True,
                "notes": "制版工序优先分派给设计部",
            },
        )


def align_role_department_presets(apps, schema_editor):
    sync_role_permissions(apps, schema_editor)
    align_department_presets(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("workorder", "0057_add_approve_permission"),
    ]

    operations = [
        migrations.RunPython(
            align_role_department_presets,
            migrations.RunPython.noop,
        ),
    ]
