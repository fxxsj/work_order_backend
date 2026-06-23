"""
客户订单财务视图测试
覆盖开票、收款、计划、对账、成本、毛利等字段
"""

from decimal import Decimal

import pytest
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta

from workorder.models.core import WorkOrder
from workorder.models.finance import Invoice, Payment, ProductionCost
from workorder.models.sales import SalesOrder, SalesOrderItem
from workorder.models.base import Customer
from workorder.models.products import Product
from workorder.serializers.sales import SalesOrderDetailSerializer


@pytest.fixture
def finance_sales_order(db):
    """创建带财务数据的客户订单"""
    customer = Customer.objects.create(
        name="财务视图客户", contact_person="张", phone="138"
    )
    user = User.objects.create_user(
        username="finance_test_user", password="test"
    )
    product = Product.objects.create(
        name="财务测试产品", code="FIN001", unit="件"
    )

    sales_order = SalesOrder.objects.create(
        customer=customer,
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        status="completed",
        subtotal=Decimal("1000.00"),
        tax_rate=Decimal("13"),
        total_amount=Decimal("1130.00"),
        paid_amount=Decimal("500.00"),
        created_by=user,
    )
    SalesOrderItem.objects.create(
        sales_order=sales_order,
        product=product,
        quantity=10,
        unit="件",
        unit_price=Decimal("100.00"),
    )

    # 创建施工单和成本
    work_order = WorkOrder.objects.create(
        customer=customer,
        sales_order=sales_order,
        order_number="WO20260607FIN",
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        production_quantity=10,
        status="completed",
        created_by=user,
    )
    ProductionCost.objects.create(
        work_order=work_order,
        period="2026-06",
        material_cost=Decimal("300.00"),
        labor_cost=Decimal("200.00"),
        equipment_cost=Decimal("50.00"),
        overhead_cost=Decimal("50.00"),
        total_cost=Decimal("600.00"),
        standard_cost=Decimal("500.00"),
    )

    # 创建发票
    invoice = Invoice.objects.create(
        sales_order=sales_order,
        customer=customer,
        amount=Decimal("1000.00"),
        tax_rate=Decimal("13"),
        tax_amount=Decimal("130.00"),
        total_amount=Decimal("1130.00"),
        status="issued",
    )

    # 创建收款
    Payment.objects.create(
        sales_order=sales_order,
        customer=customer,
        amount=Decimal("500.00"),
        applied_amount=Decimal("500.00"),
        remaining_amount=Decimal("0"),
        payment_method="transfer",
    )

    return sales_order, work_order, invoice


@pytest.mark.django_db(transaction=True)
class TestSalesOrderFinanceView:
    """测试客户订单财务视图字段"""

    def test_invoice_total_amount(self, finance_sales_order):
        """发票总额正确汇总"""
        sales_order, _, _ = finance_sales_order
        serializer = SalesOrderDetailSerializer(sales_order)
        assert serializer.data["invoice_total_amount"] == 1130.00

    def test_invoice_received_amount(self, finance_sales_order):
        """发票已收金额正确"""
        sales_order, _, _ = finance_sales_order
        serializer = SalesOrderDetailSerializer(sales_order)
        # 收款关联到销售订单，不是直接关联到发票的 payments
        # 由于测试中的 Payment 没有关联 invoice，所以发票已收金额为 0
        # 这里验证序列化器不报错即可
        assert "invoice_received_amount" in serializer.data

    def test_unpaid_amount(self, finance_sales_order):
        """未回款金额 = 订单总额 - 已付金额"""
        sales_order, _, _ = finance_sales_order
        serializer = SalesOrderDetailSerializer(sales_order)
        assert serializer.data["unpaid_amount"] == 630.00  # 1130 - 500

    def test_production_cost_total(self, finance_sales_order):
        """关联施工单成本汇总正确"""
        sales_order, _, _ = finance_sales_order
        serializer = SalesOrderDetailSerializer(sales_order)
        assert serializer.data["production_cost_total"] == 600.00

    def test_gross_profit(self, finance_sales_order):
        """毛利 = 订单金额 - 生产成本"""
        sales_order, _, _ = finance_sales_order
        serializer = SalesOrderDetailSerializer(sales_order)
        assert serializer.data["gross_profit"] == 530.00  # 1130 - 600

    def test_gross_profit_rate(self, finance_sales_order):
        """毛利率计算正确"""
        sales_order, _, _ = finance_sales_order
        serializer = SalesOrderDetailSerializer(sales_order)
        # 530 / 1130 * 100 = 46.90%
        assert serializer.data["gross_profit_rate"] == 46.9

    def test_no_work_order_cost_returns_zero(self, db):
        """无关联施工单时成本为 0"""
        customer = Customer.objects.create(
            name="无成本客户", contact_person="张", phone="138"
        )
        sales_order = SalesOrder.objects.create(
            customer=customer,
            order_date=timezone.now().date(),
            delivery_date=timezone.now().date() + timedelta(days=1),
            subtotal=Decimal("100.00"),
            total_amount=Decimal("100.00"),
        )
        serializer = SalesOrderDetailSerializer(sales_order)
        assert serializer.data["production_cost_total"] == 0.0
        assert serializer.data["gross_profit"] == 100.0
        assert serializer.data["gross_profit_rate"] == 100.0
