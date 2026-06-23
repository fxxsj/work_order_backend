"""同步业务角色组和权限。"""

from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from workorder.constants.role_codes import ALL_ROLE_CODES, CODE_TO_LABEL
from workorder.permissions.role_matrix import (
    ROLE_ALIASES,
    ROLE_CUSTOM_PERMISSIONS,
    ROLE_PERMISSIONS,
    STALE_PERMISSION_MODELS,
)


class Command(BaseCommand):
    help = "按预设矩阵同步系统业务角色组和权限"

    def handle(self, *args, **options):
        create_permissions(
            apps.get_app_config("workorder"),
            verbosity=0,
            apps=apps,
        )

        for role_code, model_actions in ROLE_PERMISSIONS.items():
            group, _ = Group.objects.get_or_create(name=role_code)
            group.permissions.clear()

            for model_name, actions in model_actions.items():
                model = apps.get_model("workorder", model_name)
                content_type = ContentType.objects.get_for_model(model)
                model_perm_name = model._meta.model_name
                for action in actions:
                    permission = Permission.objects.filter(
                        content_type=content_type,
                        codename=f"{action}_{model_perm_name}",
                    ).first()
                    if permission:
                        group.permissions.add(permission)

            for model_name, codenames in ROLE_CUSTOM_PERMISSIONS.get(
                role_code, {}
            ).items():
                model = apps.get_model("workorder", model_name)
                content_type = ContentType.objects.get_for_model(model)
                for codename in codenames:
                    permission = Permission.objects.filter(
                        content_type=content_type,
                        codename=codename,
                    ).first()
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
        Permission.objects.filter(
            content_type__in=stale_content_types
        ).delete()
        stale_content_types.delete()

        self.stdout.write(self.style.SUCCESS("业务角色组已同步:"))
        for code in ALL_ROLE_CODES:
            group = Group.objects.get(name=code)
            label = CODE_TO_LABEL.get(code, code)
            self.stdout.write(
                f"  - {code}（{label}）: {group.permissions.count()} 个权限"
            )
