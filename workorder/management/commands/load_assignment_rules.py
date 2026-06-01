"""Load preset task assignment rules."""

from django.core.management.base import BaseCommand
from django.db import transaction

from workorder.data import PRESET_ASSIGNMENT_RULES, PRESET_PROCESS_CODES
from workorder.models import Department, Process, TaskAssignmentRule


class Command(BaseCommand):
    help = "按预设配置同步任务分派规则"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="先删除预设工序相关的分派规则，再重新创建",
        )

    def handle(self, *args, **options):
        clear = options["clear"]

        with transaction.atomic():
            if clear:
                preset_processes = Process.objects.filter(code__in=PRESET_PROCESS_CODES)
                deleted_count = TaskAssignmentRule.objects.filter(
                    process__in=preset_processes
                ).delete()[0]
                self.stdout.write(f"已删除 {deleted_count} 条预设工序分派规则")

            process_map = {process.code: process for process in Process.objects.all()}
            department_map = {
                department.code: department for department in Department.objects.all()
            }

            created_count = 0
            updated_count = 0
            skipped_count = 0

            for rule_data in PRESET_ASSIGNMENT_RULES:
                process = process_map.get(rule_data["process_code"])
                department = department_map.get(rule_data["department_code"])

                if not process:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"工序编码不存在，跳过规则: {rule_data['process_code']}"
                        )
                    )
                    continue

                if not department:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"部门编码不存在，跳过规则: {rule_data['department_code']}"
                        )
                    )
                    continue

                _, created = TaskAssignmentRule.objects.update_or_create(
                    process=process,
                    department=department,
                    defaults={
                        "priority": rule_data["priority"],
                        "operator_selection_strategy": rule_data[
                            "operator_selection_strategy"
                        ],
                        "is_active": True,
                        "notes": rule_data.get("notes", ""),
                    },
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "任务分派规则同步完成: "
                f"创建 {created_count} 条，更新 {updated_count} 条，跳过 {skipped_count} 条"
            )
        )
