"""
模块级审核开关 (ApprovalConfig) 测试

验证：
- 审核开启（默认）时，提交后停留在 submitted，行为不变。
- 审核关闭时，提交后由系统自动通过（approved），并留痕。
- is_enabled() 对已知/未知模块的语义。
"""

from decimal import Decimal
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from workorder.models.base import Customer
from workorder.models.products import Product
from workorder.models.sales import SalesOrder, SalesOrderItem
from workorder.models.system import ApprovalConfig
from workorder.services.sales_order_service import SalesOrderService


@pytest.fixture
def sales_order_setup(db):
    """创建客户订单测试数据（草稿、单据完整可提交）。"""
    customer = Customer.objects.create(
        name="测试客户", contact_person="张", phone="138"
    )
    user = User.objects.create_user(username="toggle_user", password="test")
    user.is_superuser = True
    user.save()
    product = Product.objects.create(name="测试产品", code="TG001", unit="件")

    sales_order = SalesOrder.objects.create(
        customer=customer,
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        status="pending",
        approval_status="draft",
        total_amount=Decimal("1000.00"),
        created_by=user,
    )
    SalesOrderItem.objects.create(
        sales_order=sales_order,
        product=product,
        quantity=10,
        unit="件",
        unit_price=Decimal("100.00"),
    )
    return {"sales_order": sales_order, "user": user}


@pytest.mark.django_db
class TestApprovalConfigModel:
    """ApprovalConfig 模型行为"""

    def test_get_solo_is_singleton(self):
        a = ApprovalConfig.get_solo()
        b = ApprovalConfig.get_solo()
        assert a.pk == b.pk
        assert ApprovalConfig.objects.count() == 1

    def test_defaults_all_enabled(self):
        config = ApprovalConfig.get_solo()
        for model_name in ApprovalConfig.MODULE_FIELD_MAP:
            assert config.is_enabled(model_name) is True

    def test_unknown_module_defaults_enabled(self):
        config = ApprovalConfig.get_solo()
        assert config.is_enabled("unknown_module") is True


@pytest.mark.django_db
class TestApprovalToggleOnSubmit:
    """审核开关对提交流程的影响"""

    def test_submit_keeps_submitted_when_enabled(self, sales_order_setup):
        """审核开启（默认）：提交后停留在 submitted。"""
        sales_order = sales_order_setup["sales_order"]
        user = sales_order_setup["user"]

        result = SalesOrderService.submit_for_approval(
            sales_order=sales_order, user=user
        )

        assert result.approval_status == "submitted"

    def test_submit_auto_approves_when_disabled(self, sales_order_setup):
        """审核关闭：提交后系统自动通过。"""
        sales_order = sales_order_setup["sales_order"]
        user = sales_order_setup["user"]

        config = ApprovalConfig.get_solo()
        config.salesorder_approval_enabled = False
        config.save()

        result = SalesOrderService.submit_for_approval(
            sales_order=sales_order, user=user
        )

        assert result.approval_status == "approved"
        assert result.approved_by == user
        assert result.approved_at is not None
        assert "模块审核已关闭" in result.approval_comment

    def test_disabling_one_module_does_not_affect_others(
        self, sales_order_setup
    ):
        """关闭其他模块不影响客户订单审核。"""
        sales_order = sales_order_setup["sales_order"]
        user = sales_order_setup["user"]

        config = ApprovalConfig.get_solo()
        config.purchaseorder_approval_enabled = False
        config.save()

        result = SalesOrderService.submit_for_approval(
            sales_order=sales_order, user=user
        )

        assert result.approval_status == "submitted"
