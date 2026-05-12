"""
检查业务角色组是否已由迁移初始化。

角色和权限的唯一来源是 0055_normalize_role_groups 迁移。
"""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from workorder.constants.role_codes import ALL_ROLE_CODES, CODE_TO_LABEL


class Command(BaseCommand):
    help = "检查系统业务角色组"

    def handle(self, *args, **options):
        existing_codes = set(
            Group.objects.filter(name__in=ALL_ROLE_CODES).values_list("name", flat=True)
        )
        missing_codes = [code for code in ALL_ROLE_CODES if code not in existing_codes]

        if missing_codes:
            raise CommandError(
                "以下角色组尚未初始化，请先执行数据库迁移: " + ", ".join(missing_codes)
            )

        self.stdout.write(self.style.SUCCESS("业务角色组已初始化:"))
        for code in ALL_ROLE_CODES:
            group = Group.objects.get(name=code)
            label = CODE_TO_LABEL.get(code, code)
            self.stdout.write(
                f"  - {code}（{label}）: {group.permissions.count()} 个权限"
            )
