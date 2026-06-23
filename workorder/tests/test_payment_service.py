"""
PaymentService 自动化测试
覆盖收款创建/更新/删除后的订单付款状态回写
"""

from decimal import Decimal

import pytest
from django.utils import timezone
from django.contrib.auth.models import User

from workorder.models.sales import SalesOrder, SalesOrderItem
from workorder.models.finance import Payment, PaymentPlan
from workorder.models.products import Product
from workorder.models.base import Customer
from workorder.services.payment_service import PaymentService


@pytest.fixture
def customer(db):
    return Customer.objects.create(
        name="测试客户",
        contact_person="张三",
        phone="13800138000",
    )


@pytest.fixture
def product(db):
    return Product.objects.create(
        name="测试产品",
        code="TEST001",
        unit="件",
        unit_price=100.00,
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="testuser",
        password="testpass123",
        email="test@example.com",
    )


@pytest.fixture
def sales_order(db, customer, product, user):
    """创建含税总额 4068.00 的销售订单（模拟报告中的测试数据）"""
    order = SalesOrder.objects.create(
        customer=customer,
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date(),
        status="approved",
        created_by=user,
    )
    SalesOrderItem.objects.create(
        sales_order=order,
        product=product,
        quantity=200,
        unit="件",
        unit_price=18.00,
        tax_rate=13,
    )
    # 触发重新计算 total_amount
    order.update_totals()
    order.refresh_from_db()
    return order


@pytest.fixture
def payment_plan(db, sales_order):
    return PaymentPlan.objects.create(
        sales_order=sales_order,
        plan_amount=Decimal("4068.00"),
        plan_date=timezone.now().date(),
    )


@pytest.mark.django_db
class TestPaymentServiceApplyPayment:
    """测试 PaymentService.apply_payment 回写订单付款状态"""

    def test_create_full_payment_updates_order_to_paid(
        self, sales_order, user, payment_plan
    ):
        """创建全额收款后，订单付款状态变为 paid"""
        payment = Payment.objects.create(
            sales_order=sales_order,
            customer=sales_order.customer,
            amount=Decimal("4068.00"),
            applied_amount=Decimal("4068.00"),
            payment_date=timezone.now().date(),
            recorded_by=user,
        )

        PaymentService.apply_payment(payment=payment, user=user)

        sales_order.refresh_from_db()
        assert sales_order.paid_amount == Decimal("4068.00")
        assert sales_order.payment_status == "paid"
        assert sales_order.payment_date is not None

    def test_create_partial_payment_updates_order_to_partial(
        self, sales_order, user
    ):
        """创建部分收款后，订单付款状态变为 partial"""
        payment = Payment.objects.create(
            sales_order=sales_order,
            customer=sales_order.customer,
            amount=Decimal("2000.00"),
            applied_amount=Decimal("2000.00"),
            payment_date=timezone.now().date(),
            recorded_by=user,
        )

        PaymentService.apply_payment(payment=payment, user=user)

        sales_order.refresh_from_db()
        assert sales_order.paid_amount == Decimal("2000.00")
        assert sales_order.payment_status == "partial"
        assert sales_order.payment_date is None

    def test_create_zero_payment_keeps_unpaid(self, sales_order, user):
        """创建 applied_amount=0 的收款，订单保持 unpaid"""
        payment = Payment.objects.create(
            sales_order=sales_order,
            customer=sales_order.customer,
            amount=Decimal("1000.00"),
            applied_amount=Decimal("0.00"),
            payment_date=timezone.now().date(),
            recorded_by=user,
        )

        PaymentService.apply_payment(payment=payment, user=user)

        sales_order.refresh_from_db()
        assert sales_order.paid_amount == Decimal("0.00")
        assert sales_order.payment_status == "unpaid"
        assert sales_order.payment_date is None

    def test_multiple_payments_sum_correctly(self, sales_order, user):
        """多笔收款汇总正确"""
        Payment.objects.create(
            sales_order=sales_order,
            customer=sales_order.customer,
            amount=Decimal("2000.00"),
            applied_amount=Decimal("2000.00"),
            payment_date=timezone.now().date(),
            recorded_by=user,
        )
        Payment.objects.create(
            sales_order=sales_order,
            customer=sales_order.customer,
            amount=Decimal("2068.00"),
            applied_amount=Decimal("2068.00"),
            payment_date=timezone.now().date(),
            recorded_by=user,
        )

        # 重新触发计算（模拟从最后一笔 payment 调用 apply_payment）
        last_payment = Payment.objects.filter(sales_order=sales_order).last()
        PaymentService.apply_payment(payment=last_payment, user=user)

        sales_order.refresh_from_db()
        assert sales_order.paid_amount == Decimal("4068.00")
        assert sales_order.payment_status == "paid"

    def test_delete_payment_recalculates_order(self, sales_order, user):
        """删除收款后重新计算订单付款状态"""
        payment = Payment.objects.create(
            sales_order=sales_order,
            customer=sales_order.customer,
            amount=Decimal("4068.00"),
            applied_amount=Decimal("4068.00"),
            payment_date=timezone.now().date(),
            recorded_by=user,
        )
        PaymentService.apply_payment(payment=payment, user=user)
        sales_order.refresh_from_db()
        assert sales_order.payment_status == "paid"

        # 模拟删除后重算
        payment.delete()
        PaymentService._update_sales_order_payment_status(sales_order)

        sales_order.refresh_from_db()
        assert sales_order.paid_amount == Decimal("0.00")
        assert sales_order.payment_status == "unpaid"
        assert sales_order.payment_date is None

    def test_paid_to_partial_clears_payment_date(self, sales_order, user):
        """全额收款回退到部分收款时，payment_date 应清空"""
        # 先全额收款
        full_payment = Payment.objects.create(
            sales_order=sales_order,
            customer=sales_order.customer,
            amount=Decimal("4068.00"),
            applied_amount=Decimal("4068.00"),
            payment_date=timezone.now().date(),
            recorded_by=user,
        )
        PaymentService.apply_payment(payment=full_payment, user=user)
        sales_order.refresh_from_db()
        assert sales_order.payment_status == "paid"
        assert sales_order.payment_date is not None

        # 再创建退款/负向调整（通过减少 applied_amount 模拟）
        full_payment.applied_amount = Decimal("2000.00")
        full_payment.save()
        PaymentService.apply_payment(payment=full_payment, user=user)

        sales_order.refresh_from_db()
        assert sales_order.payment_status == "partial"
        assert sales_order.payment_date is None

    def test_payment_without_sales_order_skips_rewrite(self, customer, user):
        """未关联销售订单的收款跳过回写"""
        payment = Payment.objects.create(
            customer=customer,
            amount=Decimal("1000.00"),
            applied_amount=Decimal("1000.00"),
            payment_date=timezone.now().date(),
            recorded_by=user,
        )

        result = PaymentService.apply_payment(payment=payment, user=user)
        assert result == payment

    def test_payment_plan_distribution(self, sales_order, user, payment_plan):
        """收款后收款计划按 FIFO 分配"""
        payment = Payment.objects.create(
            sales_order=sales_order,
            customer=sales_order.customer,
            amount=Decimal("2000.00"),
            applied_amount=Decimal("2000.00"),
            payment_date=timezone.now().date(),
            recorded_by=user,
        )

        PaymentService.apply_payment(payment=payment, user=user)

        payment_plan.refresh_from_db()
        assert payment_plan.paid_amount == Decimal("2000.00")
        assert payment_plan.status == "partial"

    def test_full_payment_plan_completed(
        self, sales_order, user, payment_plan
    ):
        """全额收款后收款计划变为 completed"""
        payment = Payment.objects.create(
            sales_order=sales_order,
            customer=sales_order.customer,
            amount=Decimal("4068.00"),
            applied_amount=Decimal("4068.00"),
            payment_date=timezone.now().date(),
            recorded_by=user,
        )

        PaymentService.apply_payment(payment=payment, user=user)

        payment_plan.refresh_from_db()
        assert payment_plan.paid_amount == Decimal("4068.00")
        assert payment_plan.status == "completed"
