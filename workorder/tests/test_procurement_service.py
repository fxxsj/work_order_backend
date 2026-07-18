from datetime import date, timedelta
from decimal import Decimal

import pytest

from workorder.services.procurement_service import ProcurementService
from workorder.tests.factories import (
    MaterialFactory,
    SupplierFactory,
    WorkOrderFactory,
    WorkOrderMaterialFactory,
)


@pytest.mark.django_db
class TestProcurementService:
    def test_summary_groups_confirmed_requirement_by_resolved_stock_sku(self):
        requirement_supplier = SupplierFactory(name="需求默认供应商")
        stock_supplier = SupplierFactory(name="大度纸供应商")
        requirement = MaterialFactory(
            name="300G单铜",
            specification_level="requirement",
            material_type="paper",
            default_supplier=requirement_supplier,
        )
        stock = MaterialFactory(
            name="300G单铜 大度",
            specification_level="stock",
            base_material=requirement,
            material_type="paper",
            default_supplier=stock_supplier,
            unit="张",
        )
        work_order = WorkOrderFactory(
            approval_status="approved",
            status="pending",
        )
        WorkOrderMaterialFactory(
            work_order=work_order,
            material=requirement,
            purchase_material=stock,
            calculation_mode="sheet_imposition",
            preparation_mode="supplier_cutting",
            planning_required=True,
            planning_status="confirmed",
            planned_parent_quantity=Decimal("150.5"),
            reserved_quantity=Decimal("100"),
            purchase_quantity=Decimal("50.5"),
            material_usage="150.5张",
        )

        result = ProcurementService.get_procurement_summary()

        assert result["summary"]["planning_pending_count"] == 0
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["material_id"] == stock.id
        assert item["material_name"] == "300G单铜 大度"
        assert item["default_supplier_id"] == stock_supplier.id
        assert item["total_required"] == Decimal("150.5")
        assert item["total_to_purchase"] == Decimal("50.5")

    def test_summary_reports_unconfirmed_requirement_as_planning_pending(self):
        requirement = MaterialFactory(
            name="手挽绳",
            specification_level="requirement",
            material_type="packing",
        )
        work_order = WorkOrderFactory(
            approval_status="approved",
            status="pending",
        )
        wom = WorkOrderMaterialFactory(
            work_order=work_order,
            material=requirement,
            calculation_mode="specification_selection",
            preparation_mode="pending",
            planning_required=True,
            planning_status="draft",
        )

        result = ProcurementService.get_procurement_summary()

        assert result["items"] == []
        assert result["summary"]["planning_pending_count"] == 1
        assert result["planning_pending_items"][0]["work_order_material_id"] == wom.id

    def test_delay_warning_uses_resolved_stock_lead_time(self):
        requirement = MaterialFactory(
            specification_level="requirement",
            material_type="paper",
            lead_time_days=1,
        )
        stock = MaterialFactory(
            name="本单采购纸张",
            specification_level="stock",
            base_material=requirement,
            material_type="paper",
            lead_time_days=10,
        )
        work_order = WorkOrderFactory(
            approval_status="approved",
            status="pending",
            delivery_date=date.today() + timedelta(days=3),
        )
        WorkOrderMaterialFactory(
            work_order=work_order,
            material=requirement,
            purchase_material=stock,
            calculation_mode="sheet_imposition",
            preparation_mode="supplier_cutting",
            planning_required=True,
            planning_status="confirmed",
            purchase_quantity=Decimal("20"),
            purchase_status="pending",
        )

        result = ProcurementService.get_delay_warnings()

        assert result["total"] == 1
        assert result["warnings"][0]["material_name"] == "本单采购纸张"
        assert result["warnings"][0]["lead_time_days"] == 10
        assert result["warnings"][0]["delay_days"] == 7
