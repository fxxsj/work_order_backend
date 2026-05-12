"""
为用户分配业务角色。

运行: python manage.py assign_permissions <username> <role_code>
例如: python manage.py assign_permissions zhangsan sales
"""

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError

from workorder.constants.role_codes import ALL_ROLE_CODES, CODE_TO_LABEL


class Command(BaseCommand):
    help = "将用户添加到指定业务角色组"

    def add_arguments(self, parser):
        parser.add_argument("username", type=str, help="用户名")
        parser.add_argument(
            "role_code",
            type=str,
            help=f"角色 code：{', '.join(ALL_ROLE_CODES)}",
        )

    def handle(self, *args, **options):
        username = options["username"]
        role_code = options["role_code"]

        if role_code not in ALL_ROLE_CODES:
            raise CommandError(
                f'角色 "{role_code}" 不存在，可用角色：{", ".join(ALL_ROLE_CODES)}'
            )

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f'用户 "{username}" 不存在') from exc

        try:
            group = Group.objects.get(name=role_code)
        except Group.DoesNotExist as exc:
            raise CommandError(
                f'角色组 "{role_code}" 不存在，请先执行数据库迁移'
            ) from exc

        role_label = CODE_TO_LABEL.get(role_code, role_code)
        if user.groups.filter(name=role_code).exists():
            self.stdout.write(
                self.style.WARNING(
                    f'用户 "{username}" 已经拥有角色 "{role_code}"（{role_label}）'
                )
            )
        else:
            user.groups.add(group)
            self.stdout.write(
                self.style.SUCCESS(
                    f'成功将用户 "{username}" 添加到角色 "{role_code}"（{role_label}）'
                )
            )

        group_names = ", ".join(user.groups.values_list("name", flat=True))
        permission_count = user.user_permissions.count() + sum(
            g.permissions.count() for g in user.groups.all()
        )
        self.stdout.write("")
        self.stdout.write(f'用户 "{username}" 当前角色: {group_names}')
        self.stdout.write(f"权限数量: {permission_count}")
