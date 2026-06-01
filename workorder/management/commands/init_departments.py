"""Initialize preset departments and their process mappings."""

from django.core.management.base import BaseCommand
from django.db import transaction

from workorder.data import (
    DEPARTMENT_PROCESS_MAPPING,
    PRESET_DEPARTMENT_CODES,
    PRESET_MANAGEMENT_DEPARTMENTS,
    PRESET_PRODUCTION_DEPARTMENT,
    PRESET_WORKSHOP_DEPARTMENTS,
)
from workorder.models import Department, Process


class Command(BaseCommand):
    help = "按预设配置同步部门及部门-工序关系"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="先删除预设部门，再重新创建。仅适用于无业务数据的初始化环境",
        )

    def handle(self, *args, **options):
        clear = options["clear"]

        with transaction.atomic():
            if clear:
                deleted_count = Department.objects.filter(
                    code__in=PRESET_DEPARTMENT_CODES
                ).delete()[0]
                self.stdout.write(f"已删除 {deleted_count} 条预设部门相关记录")

            for dept_data in PRESET_MANAGEMENT_DEPARTMENTS:
                Department.objects.update_or_create(
                    code=dept_data["code"],
                    defaults={
                        "name": dept_data["name"],
                        "sort_order": dept_data["sort_order"],
                        "is_active": True,
                        "parent": None,
                    },
                )

            production_dept, _ = Department.objects.update_or_create(
                code=PRESET_PRODUCTION_DEPARTMENT["code"],
                defaults={
                    "name": PRESET_PRODUCTION_DEPARTMENT["name"],
                    "sort_order": PRESET_PRODUCTION_DEPARTMENT["sort_order"],
                    "is_active": True,
                    "parent": None,
                },
            )

            for dept_data in PRESET_WORKSHOP_DEPARTMENTS:
                Department.objects.update_or_create(
                    code=dept_data["code"],
                    defaults={
                        "name": dept_data["name"],
                        "sort_order": dept_data["sort_order"],
                        "is_active": True,
                        "parent": production_dept,
                    },
                )

            configured_count = 0
            skipped_count = 0
            for dept_code, process_codes in DEPARTMENT_PROCESS_MAPPING.items():
                department = Department.objects.filter(code=dept_code).first()
                if not department:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"部门编码不存在，跳过工序关联: {dept_code}")
                    )
                    continue

                processes = Process.objects.filter(code__in=process_codes, is_active=True)
                department.processes.set(processes)
                configured_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "部门初始化完成: "
                f"预设部门 {len(PRESET_DEPARTMENT_CODES)} 个，"
                f"配置工序关联 {configured_count} 个，跳过 {skipped_count} 个"
            )
        )
