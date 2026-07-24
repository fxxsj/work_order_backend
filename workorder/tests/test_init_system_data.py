"""系统基础数据初始化命令测试。"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase

from workorder.constants.role_codes import ALL_ROLE_CODES
from workorder.data import (
    DEPARTMENT_PROCESS_MAPPING,
    PRESET_ASSIGNMENT_RULES,
    PRESET_DEPARTMENT_CODES,
    PRESET_PROCESS_CODES,
)
from workorder.models import Department, Process, Product, TaskAssignmentRule


class InitSystemDataCommandTest(TestCase):
    def test_syncs_required_system_data_without_demo_records(self):
        call_command("init_system_data", verbosity=0)

        self.assertEqual(
            Process.objects.filter(code__in=PRESET_PROCESS_CODES).count(),
            len(PRESET_PROCESS_CODES),
        )
        self.assertEqual(
            Department.objects.filter(code__in=PRESET_DEPARTMENT_CODES).count(),
            len(PRESET_DEPARTMENT_CODES),
        )
        self.assertEqual(
            Group.objects.filter(name__in=ALL_ROLE_CODES).count(),
            len(ALL_ROLE_CODES),
        )
        self.assertEqual(
            TaskAssignmentRule.objects.filter(
                process__code__in=PRESET_PROCESS_CODES,
                department__code__in=PRESET_DEPARTMENT_CODES,
            ).count(),
            len(PRESET_ASSIGNMENT_RULES),
        )

        self.assertEqual(get_user_model().objects.count(), 0)
        self.assertEqual(Product.objects.count(), 0)

    def test_is_idempotent_and_preserves_custom_data(self):
        custom_process = Process.objects.create(
            code="CUSTOM",
            name="自定义工序",
        )
        custom_department = Department.objects.create(
            code="custom",
            name="自定义部门",
        )
        custom_rule = TaskAssignmentRule.objects.create(
            process=custom_process,
            department=custom_department,
            priority=42,
        )

        call_command("init_system_data", verbosity=0)
        call_command("init_system_data", verbosity=0)

        self.assertTrue(Process.objects.filter(pk=custom_process.pk).exists())
        self.assertTrue(Department.objects.filter(pk=custom_department.pk).exists())
        self.assertTrue(TaskAssignmentRule.objects.filter(pk=custom_rule.pk).exists())
        self.assertEqual(
            Process.objects.filter(code__in=PRESET_PROCESS_CODES).count(),
            len(PRESET_PROCESS_CODES),
        )
        self.assertEqual(
            TaskAssignmentRule.objects.filter(
                process__code__in=PRESET_PROCESS_CODES,
                department__code__in=PRESET_DEPARTMENT_CODES,
            ).count(),
            len(PRESET_ASSIGNMENT_RULES),
        )

    def test_preserves_existing_customizations_while_filling_missing_data(self):
        Process.objects.create(
            code="PRT",
            name="自定义印刷",
            requires_artwork=False,
            is_active=False,
        )
        printing = Department.objects.create(
            code="printing",
            name="印刷一部",
        )

        call_command("init_system_data", verbosity=0)

        process = Process.objects.get(code="PRT")
        printing.refresh_from_db()
        self.assertEqual(process.name, "自定义印刷")
        self.assertFalse(process.requires_artwork)
        self.assertFalse(process.is_active)
        self.assertEqual(printing.name, "印刷一部")
        self.assertEqual(
            set(printing.processes.values_list("code", flat=True)),
            set(DEPARTMENT_PROCESS_MAPPING["printing"]),
        )

        rule = TaskAssignmentRule.objects.get(
            process__code="PRT",
            department__code="printing",
        )
        rule.priority = 50
        rule.save(update_fields=["priority"])

        call_command("init_system_data", verbosity=0)

        rule.refresh_from_db()
        self.assertEqual(rule.priority, 50)
