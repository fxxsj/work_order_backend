"""同步正式环境所需的系统基础数据。

该命令只同步系统结构性数据，不创建测试用户、示例产品或演示业务数据：
- 业务角色组与权限
- 预设工序
- 预设部门及部门-工序关系
- 任务分派规则
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from workorder.data import (
    DEPARTMENT_PROCESS_MAPPING,
    PRESET_ASSIGNMENT_RULES,
    PRESET_MANAGEMENT_DEPARTMENTS,
    PRESET_PROCESSES,
    PRESET_PRODUCTION_DEPARTMENT,
    PRESET_WORKSHOP_DEPARTMENTS,
)
from workorder.models import Department, Process, TaskAssignmentRule


class Command(BaseCommand):
    help = "幂等同步生产环境所需的角色、工序、部门和任务分派规则"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("正在同步系统基础数据...")

        call_command("init_groups", verbosity=0)
        process_count = self._create_missing_processes()
        department_count = self._create_missing_departments()
        mapping_count = self._add_missing_department_processes()
        rule_count = self._create_missing_assignment_rules()

        self.stdout.write(
            self.style.SUCCESS(
                "系统基础数据同步完成: "
                f"新增工序 {process_count} 个、"
                f"新增部门 {department_count} 个、"
                f"补充部门工序关联 {mapping_count} 条、"
                f"新增分派规则 {rule_count} 条"
            )
        )

    def _create_missing_processes(self):
        created_count = 0

        for process_data in PRESET_PROCESSES:
            defaults = {
                "name": process_data["name"],
                "description": process_data.get("description", ""),
                "standard_duration": process_data.get("standard_duration", 0),
                "sort_order": process_data.get("sort_order", 0),
                "is_active": process_data.get("is_active", True),
                "is_builtin": True,
                "task_generation_rule": process_data.get(
                    "task_generation_rule", "general"
                ),
                "requires_artwork": process_data.get("requires_artwork", False),
                "requires_die": process_data.get("requires_die", False),
                "requires_foiling_plate": process_data.get(
                    "requires_foiling_plate", False
                ),
                "requires_embossing_plate": process_data.get(
                    "requires_embossing_plate", False
                ),
                "artwork_required": process_data.get("artwork_required", True),
                "die_required": process_data.get("die_required", True),
                "foiling_plate_required": process_data.get(
                    "foiling_plate_required", True
                ),
                "embossing_plate_required": process_data.get(
                    "embossing_plate_required", True
                ),
                "is_parallel": process_data.get("is_parallel", False),
            }
            _, created = Process.objects.get_or_create(
                code=process_data["code"],
                defaults=defaults,
            )
            if created:
                created_count += 1

        return created_count

    def _create_missing_departments(self):
        created_count = 0

        for department_data in PRESET_MANAGEMENT_DEPARTMENTS:
            _, created = Department.objects.get_or_create(
                code=department_data["code"],
                defaults={
                    "name": department_data["name"],
                    "sort_order": department_data["sort_order"],
                    "is_active": True,
                    "parent": None,
                },
            )
            created_count += int(created)

        production, created = Department.objects.get_or_create(
            code=PRESET_PRODUCTION_DEPARTMENT["code"],
            defaults={
                "name": PRESET_PRODUCTION_DEPARTMENT["name"],
                "sort_order": PRESET_PRODUCTION_DEPARTMENT["sort_order"],
                "is_active": True,
                "parent": None,
            },
        )
        created_count += int(created)

        for department_data in PRESET_WORKSHOP_DEPARTMENTS:
            department, created = Department.objects.get_or_create(
                code=department_data["code"],
                defaults={
                    "name": department_data["name"],
                    "sort_order": department_data["sort_order"],
                    "is_active": True,
                    "parent": production,
                },
            )
            created_count += int(created)
            if not created and department.parent_id is None:
                department.parent = production
                department.save(update_fields=["parent"])

        return created_count

    def _add_missing_department_processes(self):
        added_count = 0

        for department_code, process_codes in DEPARTMENT_PROCESS_MAPPING.items():
            department = Department.objects.get(code=department_code)
            existing_codes = set(
                department.processes.filter(code__in=process_codes).values_list(
                    "code", flat=True
                )
            )
            missing_codes = set(process_codes) - existing_codes
            if missing_codes:
                department.processes.add(
                    *Process.objects.filter(code__in=missing_codes)
                )
                added_count += len(missing_codes)

        return added_count

    def _create_missing_assignment_rules(self):
        created_count = 0
        processes = {process.code: process for process in Process.objects.all()}
        departments = {
            department.code: department for department in Department.objects.all()
        }

        for rule_data in PRESET_ASSIGNMENT_RULES:
            _, created = TaskAssignmentRule.objects.get_or_create(
                process=processes[rule_data["process_code"]],
                department=departments[rule_data["department_code"]],
                defaults={
                    "priority": rule_data["priority"],
                    "operator_selection_strategy": rule_data[
                        "operator_selection_strategy"
                    ],
                    "is_active": True,
                    "notes": rule_data.get("notes", ""),
                },
            )
            created_count += int(created)

        return created_count
