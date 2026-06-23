"""最小可用环境初始化命令。

一键完成新环境到可登录、可演示所需的全部基础数据：
- 执行数据库迁移
- 同步业务角色组与权限
- 加载预设工序（仅当工序表为空时）
- 同步预设部门及工序关联
- 同步任务分派规则
- 从 fixtures 加载初始用户并关联部门/角色
- 填充演示数据（客户、产品、客户订单、施工单、任务等）

用法：
    cd backend
    python manage.py bootstrap_demo
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from workorder.models import Process


class Command(BaseCommand):
    help = "初始化最小可用演示环境"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-migrate",
            action="store_true",
            help="跳过数据库迁移（迁移已执行时可用）",
        )
        parser.add_argument(
            "--skip-demo-data",
            action="store_true",
            help="跳过演示业务数据填充",
        )

    def handle(self, *args, **options):
        if not options["skip_migrate"]:
            self._step("执行数据库迁移", "migrate")

        self._step("同步业务角色组与权限", "init_groups")

        if Process.objects.count() == 0:
            self._step(
                "加载预设工序",
                "reset_processes",
                "--allow-non-debug",
            )
        else:
            self.stdout.write(
                self.style.WARNING("工序数据已存在，跳过 reset_processes")
            )

        self._step("同步预设部门", "init_departments")
        self._step("同步任务分派规则", "load_assignment_rules")

        if not self._has_initial_users():
            self._step("加载初始用户", "load_initial_users")
        else:
            self.stdout.write(
                self.style.WARNING("初始用户已存在，跳过 load_initial_users")
            )

        if not options["skip_demo_data"]:
            self._step(
                "填充演示业务数据",
                "seed_data",
                "--allow-non-debug",
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("演示环境初始化完成！"))
        self.stdout.write("")
        self.stdout.write("可登录账号：")
        self.stdout.write("  - 超级管理员: admin_seed / 123456")
        self.stdout.write("  - 业务员: business_user / 123456")
        self.stdout.write("  - 生产主管: production_user / 123456")
        self.stdout.write("  - 操作员: printing_user / 123456")
        self.stdout.write("")

    def _step(self, label: str, command: str, *args):
        self.stdout.write(self.style.NOTICE(f"[{label}] ..."))
        call_command(command, *args, verbosity=0)
        self.stdout.write(self.style.SUCCESS(f"✓ {label}完成"))

    def _has_initial_users(self) -> bool:
        User = get_user_model()
        return User.objects.filter(
            username__in=[
                "business_user",
                "production_user",
                "printing_user",
            ]
        ).exists()
