"""库存模块审核开关测试（入库单 / 出库单）。"""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from workorder.models.base import Customer
from workorder.models.core import WorkOrder, WorkOrderProduct
from workorder.models.inventory import StockIn, StockOut
from workorder.models.products import Product
from workorder.models.system import ApprovalConfig
from workorder.services.inventory_service import StockInService, StockOutService


@pytest.fixture
def inventory_setup(db):
    customer = Customer.objects.create(
        name="库存测试客户", contact_person="张", phone="138"
    )
    user = User.objects.create_user(
        username="stock_toggle_user", password="test", is_superuser=True
    )
    work_order = WorkOrder.objects.create(
        customer=customer,
        order_number="WOST20260607001",
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        production_quantity=100,
        created_by=user,
    )
    product = Product.objects.create(
        name="库存测试产品", code="STP001", unit="件"
    )
    WorkOrderProduct.objects.create(
        work_order=work_order, product=product, quantity=50
    )
    return {"work_order": work_order, "user": user, "product": product}


@pytest.mark.django_db
class TestStockInApprovalToggle:
    """入库单审核开关"""

    def test_submit_keeps_submitted_when_enabled(self, inventory_setup):
        work_order = inventory_setup["work_order"]
        user = inventory_setup["user"]
        stock_in = StockIn.objects.create(work_order=work_order)

        result = StockInService.submit(stock_in=stock_in, user=user)

        assert result.status == "submitted"

    def test_submit_auto_confirms_when_disabled(self, inventory_setup):
        work_order = inventory_setup["work_order"]
        user = inventory_setup["user"]
        config = ApprovalConfig.get_solo()
        config.stockin_approval_enabled = False
        config.save()

        stock_in = StockIn.objects.create(work_order=work_order)

        result = StockInService.submit(stock_in=stock_in, user=user)

        assert result.status == "completed"
        assert result.confirmed_by == user
        assert result.confirmed_at is not None


@pytest.mark.django_db
class TestStockOutApprovalToggle:
    """出库单审核开关（提交阶段；自动确认依赖送货单，单独验证）。"""

    def test_submit_keeps_submitted_when_enabled(self, inventory_setup):
        user = inventory_setup["user"]
        stock_out = StockOut.objects.create(out_type="delivery")

        result = StockOutService.submit(stock_out=stock_out, user=user)

        assert result.status == "submitted"

    def test_submit_auto_confirms_path_triggered(self, inventory_setup):
        """审核关闭时，提交会尝试进入 confirm 流程（路径覆盖）。

        confirm 内部会校验送货单；这里重点验证开关触发了自动确认分支，
        因此会抛出送货单相关校验错误而非停留在 submitted。
        """
        user = inventory_setup["user"]
        config = ApprovalConfig.get_solo()
        config.stockout_approval_enabled = False
        config.save()

        stock_out = StockOut.objects.create(out_type="delivery")

        # confirm 会因为没有 delivery_order 报错，证明分支已触发
        with pytest.raises(Exception):
            StockOutService.submit(stock_out=stock_out, user=user)
