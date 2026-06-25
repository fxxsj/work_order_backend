"""审核开关配置 API 测试。"""

from django.test import TestCase
from django.urls import reverse

from .conftest import APITestCaseMixin, TestDataFactory
from ..models.system import ApprovalConfig


class ApprovalConfigAPITest(APITestCaseMixin, TestCase):
    """GET/PUT /api/v1/approval-config/"""

    def setUp(self):
        super().setUp()
        self.admin = TestDataFactory.create_user(
            username="approval_admin", is_superuser=True
        )
        self.normal = TestDataFactory.create_user(
            username="approval_normal", is_staff=False
        )
        self.url = reverse("approval-config")

    def test_get_returns_defaults_all_enabled(self):
        response = self.api_get(self.url, user=self.admin)
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertTrue(data["workorder_approval_enabled"])
        self.assertTrue(data["salesorder_approval_enabled"])

    def test_get_allowed_for_normal_user(self):
        """已登录用户可读取（供前端按钮联动）。"""
        response = self.api_get(self.url, user=self.normal)
        self.assertEqual(response.status_code, 200)

    def test_get_requires_auth(self):
        response = self.api_get(self.url)
        self.assertIn(response.status_code, (401, 403))

    def test_put_updates_switch(self):
        response = self.api_put(
            self.url,
            {"purchaseorder_approval_enabled": False},
            user=self.admin,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            response.data["data"]["purchaseorder_approval_enabled"]
        )
        config = ApprovalConfig.get_solo()
        self.assertFalse(config.purchaseorder_approval_enabled)
        # 未提交字段保持默认
        self.assertTrue(config.workorder_approval_enabled)

    def test_put_forbidden_for_normal_user(self):
        response = self.api_put(
            self.url,
            {"workorder_approval_enabled": False},
            user=self.normal,
        )
        self.assertEqual(response.status_code, 403)
        # 未被修改
        self.assertTrue(ApprovalConfig.get_solo().workorder_approval_enabled)
