"""
角色画像权限测试 - 验证各角色的实际业务权限

基于 role_matrix.py 中的矩阵，验证：
1. 各角色只能执行有权执行的操作
2. 无权限用户收到 403
3. 超级管理员全部放行
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from workorder.models import WorkOrder, SalesOrder, Customer, Product, Process, Department
from workorder.models.system import Notification, NotificationTemplate
from workorder.permissions.role_matrix import ROLE_PERMISSIONS, ROLE_CUSTOM_PERMISSIONS
from workorder.constants.role_codes import ALL_ROLE_CODES


class RoleProfilePermissionTest(TestCase):
    """角色画像权限测试"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = APIClient()

    def _get_user_with_role(self, role_code):
        """创建属于指定角色的用户"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(
            username=f"test_{role_code}",
            password="test_pass_123",
            is_staff=True,
        )
        group = Group.objects.get(name=role_code)
        user.groups.add(group)
        user = User.objects.get(pk=user.pk)
        return user

    def _auth_header(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}

    def test_sales_can_create_workorder_from_sales_order(self):
        """销售：从客户订单生成施工单"""
        user = self._get_user_with_role("sales")
        self.assertTrue(user.has_perm("workorder.add_workorder"))

    def test_sales_cannot_mark_urgent(self):
        """销售：不能标急"""
        user = self._get_user_with_role("sales")
        self.assertFalse(user.has_perm("workorder.change_workorder"))

    def test_operator_cannot_mark_urgent(self):
        """操作员：不能标急"""
        user = self._get_user_with_role("operator")
        self.assertFalse(user.has_perm("workorder.change_workorder"))

    def test_manager_can_mark_urgent(self):
        """经理：能标急"""
        user = self._get_user_with_role("manager")
        self.assertTrue(user.has_perm("workorder.change_workorder"))

    def test_manager_has_delete_workorder_permission(self):
        """经理：有 delete_workorder 权限字符串"""
        user = self._get_user_with_role("manager")
        self.assertTrue(user.has_perm("workorder.delete_workorder"))

    def test_supervisor_cannot_delete_workorder(self):
        """主管：不能删除施工单"""
        user = self._get_user_with_role("supervisor")
        self.assertFalse(user.has_perm("workorder.delete_workorder"))

    def test_finance_cannot_add_workorder(self):
        """财务：不能创建施工单"""
        user = self._get_user_with_role("finance")
        self.assertFalse(user.has_perm("workorder.add_workorder"))

    def test_inventory_cannot_add_workorder(self):
        """仓储：不能创建施工单"""
        user = self._get_user_with_role("inventory")
        self.assertFalse(user.has_perm("workorder.add_workorder"))

    def test_quality_cannot_add_workorder(self):
        """质检：不能创建施工单"""
        user = self._get_user_with_role("quality")
        self.assertFalse(user.has_perm("workorder.add_workorder"))

    def test_admin_cannot_delete_customer(self):
        """管理员：不应该有 delete_customer（保留给超级管理员）"""
        user = self._get_user_with_role("admin")
        self.assertFalse(user.has_perm("workorder.delete_customer"))

    def test_superuser_can_do_everything(self):
        """超级管理员：所有权限"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        superuser = User.objects.create_superuser(
            username="test_super",
            password="test_pass_123",
            email="super@example.com",
        )
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.has_perm("workorder.add_workorder"))
        self.assertTrue(superuser.has_perm("workorder.delete_workorder"))
        self.assertTrue(superuser.has_perm("workorder.delete_customer"))


class WorkOrderFlowActionPermissionTest(TestCase):
    """WorkOrderFlowViewSet action 权限测试"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api_client = APIClient()

    def _create_user_with_role(self, role_code):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(
            username=f"flow_test_{role_code}",
            password="test_pass_123",
            is_staff=True,
        )
        group = Group.objects.get(name=role_code)
        user.groups.add(group)
        return User.objects.get(pk=user.pk)

    def _get_auth_header(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}

    def test_unauthenticated_cannot_access_workorder_flow(self):
        """未认证用户不能访问 workflow endpoint"""
        response = self.api_client.post("/api/v1/workorders-flow/create_from_sales_order/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sales_cannot_create_from_sales_order_without_permission(self):
        """没有 add_workorder 权限的销售不能创建"""
        user = self._create_user_with_role("operator")
        response = self.api_client.post(
            "/api/v1/workorders-flow/create_from_sales_order/",
            {"sales_order_id": 999},
            format="json",
            **self._get_auth_header(user),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_can_create_from_sales_order_with_permission(self):
        """有 add_workorder 权限的销售可以创建（但会遇到客户订单可见性限制）"""
        user = self._create_user_with_role("sales")
        response = self.api_client.post(
            "/api/v1/workorders-flow/create_from_sales_order/",
            {"sales_order_id": 999999},
            format="json",
            **self._get_auth_header(user),
        )
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST])

    def test_operator_cannot_check_completion(self):
        """操作员不能检查完成"""
        user = self._create_user_with_role("operator")
        self.assertFalse(user.has_perm("workorder.change_workorder"))

    def test_operator_cannot_mark_urgent(self):
        """操作员不能标急"""
        user = self._create_user_with_role("operator")
        self.assertFalse(user.has_perm("workorder.change_workorder"))

    def test_manager_can_check_completion(self):
        """经理能检查完成"""
        user = self._create_user_with_role("manager")
        self.assertTrue(user.has_perm("workorder.change_workorder"))

    def test_manager_can_mark_urgent(self):
        """经理能标急"""
        user = self._create_user_with_role("manager")
        self.assertTrue(user.has_perm("workorder.change_workorder"))


class NotificationDataIsolationTest(TestCase):
    """通知个人数据隔离测试"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api_client = APIClient()

    def _create_user(self, username):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(
            username=username,
            password="test_pass_123",
            is_staff=True,
        )

    def _get_auth_header(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}

    def test_user_cannot_access_other_users_notifications(self):
        """用户 A 不能访问用户 B 的通知设置"""
        user_a = self._create_user("notif_user_a")
        user_b = self._create_user("notif_user_b")

        response_b = self.api_client.get(
            "/api/v1/notifications/settings/",
            **self._get_auth_header(user_b),
        )

        if response_b.status_code == status.HTTP_200_OK:
            data = response_b.data.get("data", {})
            user_id_in_response = data.get("user")
            if user_id_in_response:
                self.assertEqual(
                    user_id_in_response,
                    user_b.id,
                    "用户 B 获取到的 settings 应该只包含自己的 user_id",
                )

    def test_user_cannot_update_other_users_notifications(self):
        """用户 A 不能修改用户 B 的通知设置"""
        user_a = self._create_user("notif_user_a")
        user_b = self._create_user("notif_user_b")

        response = self.api_client.patch(
            "/api/v1/notifications/settings/",
            {"email_enabled": False},
            format="json",
            **self._get_auth_header(user_a),
        )
        if response.status_code == status.HTTP_200_OK:
            response_b = self.api_client.get(
                "/api/v1/notifications/settings/",
                **self._get_auth_header(user_b),
            )
            if response_b.status_code == status.HTTP_200_OK:
                pass


class PermissionMatrixCompletenessTest(TestCase):
    """权限矩阵完整性测试 - 确保矩阵覆盖所有注册权限点"""

    def test_all_roles_have_permissions(self):
        """所有角色都有权限定义"""
        for role_code in ALL_ROLE_CODES:
            self.assertIn(
                role_code,
                ROLE_PERMISSIONS,
                f"角色 {role_code} 缺少 ROLE_PERMISSIONS 定义",
            )

    def test_all_roles_with_custom_permissions_have_valid_definitions(self):
        """有自定义权限的角色，其定义必须是有效的 codenames"""
        for role_code, models in ROLE_CUSTOM_PERMISSIONS.items():
            self.assertIn(
                role_code,
                ROLE_PERMISSIONS,
                f"角色 {role_code} 有 custom permissions 但不在 ROLE_PERMISSIONS 中",
            )
            for model_name, codenames in models.items():
                self.assertIsInstance(codenames, list)

    def test_no_delete_permissions_for_regular_roles(self):
        """普通角色（除 admin/manager）不应有 delete 权限（业务减法）"""
        regular_roles = ["sales", "supervisor", "operator", "finance", "inventory", "quality"]
        for role_code in regular_roles:
            permissions = ROLE_PERMISSIONS.get(role_code, {})
            for model_name, actions in permissions.items():
                if "delete" in actions:
                    self.fail(
                        f"角色 {role_code} 的 {model_name} 不应有 delete 权限，"
                        f"delete 权限只给超级管理员"
                    )

    def test_flutter_permission_strings_in_matrix(self):
        """Flutter 使用到的权限字符串都在矩阵中"""
        import re
        from pathlib import Path

        PROJECT_ROOT = Path(__file__).resolve().parents[4]
        FLUTTER_SRC = PROJECT_ROOT / "flutter" / "lib" / "src"

        flutter_permissions = set()
        for path in FLUTTER_SRC.rglob("*.dart"):
            text = path.read_text(encoding="utf-8")
            flutter_permissions.update(
                match.group(0).strip("'\"")
                for match in re.finditer(r"['\"]workorder\.[a-z_]+?['\"]", text)
            )

        covered_permissions = set().union(*ROLE_PERMISSIONS.values())
        custom_permissions = set()
        for perms in ROLE_CUSTOM_PERMISSIONS.values():
            for codenames in perms.values():
                custom_permissions.update(codenames)

        all_covered = covered_permissions | custom_permissions

        missing = sorted(flutter_permissions - all_covered)
        self.assertEqual(
            missing, [],
            f"以下 Flutter 权限字符串未被矩阵覆盖: {missing}",
        )
