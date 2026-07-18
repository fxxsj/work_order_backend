import pytest

from workorder.serializers.core import WorkOrderMaterialSerializer
from workorder.serializers.materials import (
    MaterialSupplierSerializer,
    PurchaseOrderItemSerializer,
    PurchaseReceiveRecordSerializer,
)
from workorder.tests.factories import (
    MaterialFactory,
    MaterialSupplierFactory,
    PurchaseOrderItemFactory,
    PurchaseReceiveRecordFactory,
    WorkOrderMaterialFactory,
)


@pytest.mark.django_db
def test_purchase_serializers_expose_concrete_material_specification():
    material = MaterialFactory(specification="大度 889×1194mm")
    item = PurchaseOrderItemFactory(material=material)
    record = PurchaseReceiveRecordFactory(purchase_order_item=item)
    record.refresh_from_db()
    relation = MaterialSupplierFactory(material=material)

    assert PurchaseOrderItemSerializer(item).data["material_specification"] == (
        "大度 889×1194mm"
    )
    assert (
        PurchaseReceiveRecordSerializer(record).data["material_specification"]
        == "大度 889×1194mm"
    )
    assert MaterialSupplierSerializer(relation).data["material_specification"] == (
        "大度 889×1194mm"
    )


@pytest.mark.django_db
def test_work_order_procurement_exposes_resolved_material_specification():
    requirement = MaterialFactory(
        name="300G单铜",
        specification="",
        specification_level="requirement",
    )
    concrete_material = MaterialFactory(
        name="300G单铜",
        specification="特规 700×1000mm",
        specification_level="stock",
        base_material=requirement,
    )
    work_order_material = WorkOrderMaterialFactory(
        material=requirement,
        purchase_material=concrete_material,
        planning_required=True,
        planning_status="confirmed",
        planned_material_quantity=100,
        purchase_quantity=100,
    )

    data = WorkOrderMaterialSerializer(work_order_material).data

    assert data["procurement_material_name"] == "300G单铜"
    assert data["procurement_material_specification"] == "特规 700×1000mm"
