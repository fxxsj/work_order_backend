"""
采购实际单价进入材料成本测试
"""
from decimal import Decimal

import pytest
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta

from workorder.models.core import WorkOrder, WorkOrderMaterial
from workorder.models.materials import (
    Material,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceiveRecord,
    Supplier,
)
from workorder.models.base import Customer
from workorder.models.finance import ProductionCost
from workorder.constants.status import MaterialPurchaseStatus


@pytest.fixture
def purchase_setup(db):
    customer = Customer.objects.create(name="测试客户", contact_person="张", phone="138")
    user = User.objects.create_user(username="purchase_test_user", password="test")
    supplier = Supplier.objects.create(name="测试供应商", code="SUP001")
    material = Material.objects.create(
        name="灰板纸", code="MAT001", unit_price=Decimal("10.00"), need_cutting=True
    )
    work_order = WorkOrder.objects.create(
        customer=customer,
        order_number="WO20260607001",
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        production_quantity=100,
        created_by=user,
    )
    wom = WorkOrderMaterial.objects.create(
        work_order=work_order,
        material=material,
        need_cutting=True,
        material_usage="100张",
        purchase_status=MaterialPurchaseStatus.ORDERED,
    )
    po = PurchaseOrder.objects.create(
        supplier=supplier,
        order_number="PO20260607001",
        status="approved",
    )
    poi = PurchaseOrderItem.objects.create(
        purchase_order=po,
        material=material,
        quantity=Decimal("100"),
        unit_price=Decimal("12.50"),
        work_order_material=wom,
    )
    return work_order, wom, material, po, poi, user


@pytest.mark.django_db(transaction=True)
class TestPurchaseActualPrice:
    """测试采购实际单价回写和成本计算"""

    def test_stock_in_writes_actual_unit_price(self, purchase_setup):
        """采购入库时回写实际单价到 WorkOrderMaterial"""
        work_order, wom, material, po, poi, user = purchase_setup
        assert wom.actual_unit_price is None

        prr = PurchaseReceiveRecord.objects.create(
            purchase_order_item=poi,
            received_quantity=Decimal("100"),
            inspection_status="qualified",
            qualified_quantity=Decimal("100"),
        )
        prr.stock_in(user=user)

        wom.refresh_from_db()
        assert wom.purchase_status == MaterialPurchaseStatus.RECEIVED
        assert wom.actual_unit_price == Decimal("12.50")

    def test_actual_price_used_in_material_cost(self, purchase_setup):
        """成本核算优先使用采购实际单价"""
        work_order, wom, material, po, poi, user = purchase_setup

        # 先入库，写入实际单价 12.50
        prr = PurchaseReceiveRecord.objects.create(
            purchase_order_item=poi,
            received_quantity=Decimal("100"),
            inspection_status="qualified",
            qualified_quantity=Decimal("100"),
        )
        prr.stock_in(user=user)

        # 创建成本记录并自动计算
        cost = ProductionCost.objects.create(
            work_order=work_order,
            standard_cost=Decimal("0"),
        )
        cost.auto_calculate_material_cost()

        # material_usage="100张" 解析为 100
        # 实际单价 12.50，所以材料成本应为 1250.00
        assert cost.material_cost == Decimal("1250.00")

    def test_fallback_to_material_unit_price(self, purchase_setup):
        """没有采购实际单价时回退到物料档案单价"""
        work_order, wom, material, po, poi, user = purchase_setup

        # 不执行入库，actual_unit_price 仍为 None
        cost = ProductionCost.objects.create(
            work_order=work_order,
            standard_cost=Decimal("0"),
        )
        cost.auto_calculate_material_cost()

        # 物料档案单价 10.00，material_usage 100
        assert cost.material_cost == Decimal("1000.00")
