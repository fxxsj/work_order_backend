"""
PurchaseOrderService 测试用例

测试采购单从施工单创建、收货和取消。
"""

import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from workorder.models.base import Customer
from workorder.models.core import WorkOrder, WorkOrderMaterial
from workorder.models.materials import (
    Material,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)
from workorder.constants.status import MaterialPurchaseStatus
from workorder.services.service_errors import ServiceError
from workorder.services.purchase_order_service import PurchaseOrderService


@pytest.fixture
def purchase_setup(db):
    """创建采购单测试数据。"""
    customer = Customer.objects.create(name="测试客户", contact_person="张", phone="138")
    user = User.objects.create_user(username="po_creator", password="test")
    supplier = Supplier.objects.create(name="测试供应商", code="SUP001")
    material = Material.objects.create(
        name="测试纸张",
        code="PAPER001",
        unit="张",
        default_supplier=supplier,
        unit_price=Decimal("1.50"),
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
        material_usage="100",
        purchase_status=MaterialPurchaseStatus.PENDING,
    )

    return {
        "work_order": work_order,
        "material": material,
        "supplier": supplier,
        "wom": wom,
        "user": user,
    }


@pytest.mark.django_db
class TestPurchaseOrderService:
    """采购单服务测试"""

    def test_create_from_work_order_success(self, purchase_setup):
        """测试从施工单创建采购单成功"""
        work_order = purchase_setup["work_order"]

        result = PurchaseOrderService.create_from_work_order(
            work_order_id=work_order.id,
        )

        assert result["total_count"] == 1
        assert result["created_item_count"] == 1
        assert len(result["purchase_orders"]) == 1
        assert PurchaseOrder.objects.count() == 1

    def test_create_from_work_order_missing_supplier(self, purchase_setup):
        """测试物料缺少默认供应商时失败"""
        material = purchase_setup["material"]
        material.default_supplier = None
        material.save()

        with pytest.raises(ServiceError) as exc_info:
            PurchaseOrderService.create_from_work_order(
                work_order_id=purchase_setup["work_order"].id,
            )

        assert exc_info.value.code == 400
        assert "blocked_items" in exc_info.value.data

    def test_create_from_work_order_no_pending_materials(self, purchase_setup):
        """测试没有待采购物料时失败"""
        wom = purchase_setup["wom"]
        wom.purchase_status = MaterialPurchaseStatus.ORDERED
        wom.save()

        with pytest.raises(ServiceError) as exc_info:
            PurchaseOrderService.create_from_work_order(
                work_order_id=purchase_setup["work_order"].id,
            )

        assert exc_info.value.code == 400

    def test_cancel_purchase_order_success(self, purchase_setup):
        """测试取消采购单成功"""
        po = PurchaseOrder.objects.create(
            supplier=purchase_setup["supplier"],
            work_order=purchase_setup["work_order"],
            status="draft",
        )

        result = PurchaseOrderService.cancel(order=po)

        assert result.status == "cancelled"

    def test_cancel_already_received_order_fails(self, purchase_setup):
        """测试已收货采购单无法取消"""
        po = PurchaseOrder.objects.create(
            supplier=purchase_setup["supplier"],
            work_order=purchase_setup["work_order"],
            status="received",
        )

        with pytest.raises(ServiceError) as exc_info:
            PurchaseOrderService.cancel(order=po)

        assert exc_info.value.code == 400
