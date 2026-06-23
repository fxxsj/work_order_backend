"""
通用审批日志测试
覆盖 ApprovalService._log_approval 写入 AuditLog
"""


import pytest
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta

from workorder.models.audit import AuditLog
from workorder.models.sales import SalesOrder
from workorder.models.base import Customer
from workorder.services.approval_service import ApprovalService


@pytest.fixture
def approval_sales_order(db):
    """创建待审核的客户订单"""
    customer = Customer.objects.create(
        name="审批测试客户", contact_person="张", phone="138"
    )
    user = User.objects.create_user(
        username="approval_creator",
        password="test",
        is_staff=True,
        is_superuser=True,
    )
    approver = User.objects.create_user(
        username="approval_approver",
        password="test",
        is_staff=True,
        is_superuser=True,
    )
    sales_order = SalesOrder.objects.create(
        customer=customer,
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        status="pending",
        approval_status="draft",
        created_by=user,
    )
    return sales_order, user, approver


@pytest.mark.django_db(transaction=True)
class TestApprovalLog:
    """测试审批日志"""

    def test_submit_creates_audit_log(self, approval_sales_order):
        """提交审核应写入 AuditLog"""
        sales_order, user, approver = approval_sales_order
        service = ApprovalService(SalesOrder)
        service.submit_for_approval(sales_order, user, comment="请审核")

        logs = AuditLog.objects.filter(
            object_id=str(sales_order.pk),
            action_type=AuditLog.ACTION_UPDATE,
        )
        assert logs.count() == 1
        assert logs.first().changes["approval_action"] == "submit"
        assert logs.first().changes["comment"] == "请审核"

    def test_approve_creates_audit_log(self, approval_sales_order):
        """审核通过应写入 AuditLog"""
        sales_order, user, approver = approval_sales_order
        service = ApprovalService(SalesOrder)
        service.submit_for_approval(sales_order, user)
        service.approve(sales_order, approver, comment="同意")

        logs = AuditLog.objects.filter(
            object_id=str(sales_order.pk),
            action_type=AuditLog.ACTION_APPROVE,
        )
        assert logs.count() == 1
        assert logs.first().changes["approval_action"] == "approve"

    def test_reject_creates_audit_log(self, approval_sales_order):
        """审核拒绝应写入 AuditLog"""
        sales_order, user, approver = approval_sales_order
        service = ApprovalService(SalesOrder)
        service.submit_for_approval(sales_order, user)
        service.reject(sales_order, approver, reason="数据不完整")

        logs = AuditLog.objects.filter(
            object_id=str(sales_order.pk),
            action_type=AuditLog.ACTION_REJECT,
        )
        assert logs.count() == 1
        assert logs.first().changes["approval_action"] == "reject"
