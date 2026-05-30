"""角色与部门范围对齐测试。"""

from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.test import TestCase
from django.core.cache import cache

from workorder.constants.role_codes import ALL_ROLE_CODES
from workorder.models import Department, Process, UserProfile, WorkOrderTask
from workorder.permission_utils import PermissionCache
from workorder.services.task_assignment import TaskAssignmentService

from .conftest import TestDataFactory


class InitialUserRoleDepartmentTest(TestCase):
    """验证初始用户同时绑定部门和角色组。"""

    def test_load_initial_users_binds_departments_and_roles(self):
        call_command("init_groups", verbosity=0)
        call_command("load_initial_users", "--force", verbosity=0)

        expected_mapping = {
            "business_user": ("business", "sales"),
            "finance_user": ("finance", "finance"),
            "design_user": ("design", "design"),
            "purchase_user": ("purchase", "procurement"),
            "quality_user": ("quality", "quality"),
            "warehouse_user": ("warehouse", "inventory"),
            "production_user": ("production", "supervisor"),
            "cutting_user": ("cutting", "operator"),
            "printing_user": ("printing", "operator"),
            "outsourcing_user": ("outsourcing", "operator"),
            "die_cutting_user": ("die_cutting", "operator"),
            "packaging_user": ("packaging", "operator"),
        }

        for username, (department_code, role_code) in expected_mapping.items():
            with self.subTest(username=username):
                user = User.objects.get(username=username)
                self.assertTrue(
                    user.profile.departments.filter(code=department_code).exists()
                )
                self.assertTrue(user.groups.filter(name=role_code).exists())


class DepartmentScopeTest(TestCase):
    """验证父部门包含子部门任务范围。"""

    def setUp(self):
        cache.clear()
        self.production = Department.objects.create(
            name="生产部范围测试",
            code="scope_production",
            sort_order=1,
        )
        self.printing = Department.objects.create(
            name="印刷车间范围测试",
            code="scope_printing",
            parent=self.production,
            sort_order=2,
        )
        self.finance = Department.objects.create(
            name="财务部范围测试",
            code="scope_finance",
            sort_order=3,
        )
        self.process = Process.objects.create(
            name="范围测试工序",
            code="SCOPE_TEST",
            task_generation_rule="general",
        )
        self.printing.processes.add(self.process)

        self.supervisor = TestDataFactory.create_user(username="scope_supervisor")
        self.supervisor.groups.add(Group.objects.get(name="supervisor"))
        profile, _ = UserProfile.objects.get_or_create(user=self.supervisor)
        profile.departments.add(self.production)

        self.manager = TestDataFactory.create_user(username="scope_manager")
        self.manager.groups.add(Group.objects.get(name="manager"))

        self.work_order = TestDataFactory.create_workorder(creator=self.manager)
        self.work_order_process = TestDataFactory.create_workorder_process(
            work_order=self.work_order,
            process=self.process,
        )
        self.child_task = WorkOrderTask.objects.create(
            work_order_process=self.work_order_process,
            assigned_department=self.printing,
            work_content="子车间任务",
            status="pending",
            task_type="general",
            production_quantity=100,
        )
        self.other_task = WorkOrderTask.objects.create(
            work_order_process=self.work_order_process,
            assigned_department=self.finance,
            work_content="其他部门任务",
            status="pending",
            task_type="general",
            production_quantity=100,
        )

    def test_user_department_scope_includes_descendants(self):
        scope = PermissionCache.get_user_department_scope(self.supervisor)

        self.assertIn(self.production.id, scope)
        self.assertIn(self.printing.id, scope)
        self.assertNotIn(self.finance.id, scope)

    def test_supervisor_can_assign_child_department_task(self):
        self.assertTrue(
            TaskAssignmentService.validate_supervisor_permission(
                self.supervisor, self.child_task
            )
        )

    def test_claimable_tasks_include_child_department_tasks(self):
        operator = TestDataFactory.create_user(
            username="scope_operator",
            add_permissions=False,
        )
        profile, _ = UserProfile.objects.get_or_create(user=operator)
        profile.departments.add(self.production)

        claimable_ids = TaskAssignmentService.get_claimable_tasks_for_user(operator)

        self.assertIn(self.child_task.id, claimable_ids)
        self.assertNotIn(self.other_task.id, claimable_ids)

    def test_manager_permission_is_not_department_limited(self):
        self.assertTrue(
            TaskAssignmentService.validate_supervisor_permission(
                self.manager, self.other_task
            )
        )

    def test_all_roles_exist_for_alignment_tests(self):
        missing_roles = [
            role_code
            for role_code in ALL_ROLE_CODES
            if not Group.objects.filter(name=role_code).exists()
        ]
        self.assertEqual(missing_roles, [])
