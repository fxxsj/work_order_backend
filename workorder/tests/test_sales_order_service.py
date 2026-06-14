"""
SalesOrderService 测试用例

测试客户订单业务服务的状态流转和付款更新。
"""

from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from workorder.models.sales import SalesOrder, SalesOrderItem
from workorder.models.base import Customer
from workorder.models.products import Product
from workorder.services.sales_order_service import SalesOrderService
from workorder.services.service_errors import ServiceError


@pytest.fixture
def sales_order_setup(db):
    """创建客户订单测试数据。"""
    customer = Customer.objects.create(name="测试客户", contact_person="张", phone="138")
    user = User.objects.create_user(username="sales_test_user", password="test")
    user.is_superuser = True
    user.save()
    product = Product.objects.create(name="测试产品", code="TEST001", unit="件")

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
class TestSalesOrderService:
    """客户订单服务测试"""

    def test_submit_for_approval_success(self, sales_order_setup):
        """测试草稿状态提交审核成功"""
        sales_order = sales_order_setup["sales_order"]
        user = sales_order_setup["user"]

        result = SalesOrderService.submit_for_approval(
            sales_order=sales_order, user=user
        )

        assert result.approval_status == "submitted"
        assert result.rejection_reason == ""

    def test_submit_for_approval_invalid_status(self, sales_order_setup):
        """测试非草稿/拒绝状态提交审核失败"""
        sales_order = sales_order_setup["sales_order"]
        user = sales_order_setup["user"]
        sales_order.approval_status = "approved"
        sales_order.save()

        with pytest.raises(ServiceError) as exc_info:
            SalesOrderService.submit_for_approval(sales_order=sales_order, user=user)

        assert exc_info.value.code == 400

    def test_approve_success(self, sales_order_setup):
        """测试审核通过成功"""
        sales_order = sales_order_setup["sales_order"]
        user = sales_order_setup["user"]
        sales_order.approval_status = "submitted"
        sales_order.save()

        result = SalesOrderService.approve(
            sales_order=sales_order, user=user, comment="同意"
        )

        assert result.approval_status == "approved"
        assert result.completion_reason == ""

    def test_approve_invalid_status(self, sales_order_setup):
        """测试非提交状态审核失败"""
        sales_order = sales_order_setup["sales_order"]
        user = sales_order_setup["user"]

        with pytest.raises(ServiceError) as exc_info:
            SalesOrderService.approve(sales_order=sales_order, user=user)

        assert exc_info.value.code == 400

    def test_reject_requires_reason(self, sales_order_setup):
        """测试拒绝时原因必填"""
        sales_order = sales_order_setup["sales_order"]
        user = sales_order_setup["user"]
        sales_order.approval_status = "submitted"
        sales_order.save()

        with pytest.raises(ServiceError) as exc_info:
            SalesOrderService.reject(sales_order=sales_order, user=user, reason="")

        assert exc_info.value.code == 400

    def test_complete_sets_actual_delivery_date(self, sales_order_setup):
        """测试全部发货时自动设置实际交货日期"""
        sales_order = sales_order_setup["sales_order"]
        sales_order.approval_status = "approved"
        sales_order.status = "in_production"
        sales_order.save()

        # 模拟全部发货
        item = sales_order.items.first()
        item.delivered_quantity = item.quantity
        item.save()

        SalesOrderService.complete(sales_order=sales_order)

        sales_order.refresh_from_db()
        assert sales_order.status == "completed"
        assert sales_order.actual_delivery_date is not None

    def test_complete_requires_reason_when_not_all_delivered(self, sales_order_setup):
        """测试未全部发货时人工完结需要原因"""
        sales_order = sales_order_setup["sales_order"]
        sales_order.approval_status = "approved"
        sales_order.status = "in_production"
        sales_order.save()

        # 创建一个未发货的订单明细，模拟未全部发货
        item = sales_order.items.first()
        item.delivered_quantity = 0
        item.save()

        with pytest.raises(ServiceError) as exc_info:
            SalesOrderService.complete(sales_order=sales_order)

        assert exc_info.value.code == 400

    def test_cancel_success(self, sales_order_setup):
        """测试取消订单成功"""
        sales_order = sales_order_setup["sales_order"]

        result = SalesOrderService.cancel(
            sales_order=sales_order, reason="客户取消"
        )

        assert result.status == "cancelled"
        assert result.rejection_reason == "客户取消"

    def test_update_payment_requires_date(self, sales_order_setup):
        """测试更新付款时日期必填"""
        sales_order = sales_order_setup["sales_order"]

        with pytest.raises(ServiceError) as exc_info:
            SalesOrderService.update_payment(
                sales_order=sales_order,
                paid_amount="500.00",
                payment_date=None,
            )

        assert exc_info.value.code == 400

    def test_update_payment_success(self, sales_order_setup):
        """测试更新付款成功"""
        sales_order = sales_order_setup["sales_order"]

        result = SalesOrderService.update_payment(
            sales_order=sales_order,
            paid_amount="500.00",
            payment_date=timezone.now().date().isoformat(),
        )

        assert result.paid_amount == Decimal("500.00")
