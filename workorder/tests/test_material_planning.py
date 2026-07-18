from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework import serializers as drf_serializers
from rest_framework.test import APIClient

from workorder.models.core import WorkOrderMaterial
from workorder.services.purchase_order_service import PurchaseOrderService
from workorder.services.service_errors import ServiceError
from workorder.services.task_generation import TaskGenerationService
from workorder.services.work_order_material_service import (
    WorkOrderMaterialService,
)
from workorder.serializers.core import WorkOrderCreateUpdateSerializer
from workorder.serializers.materials import MaterialSerializer
from workorder.serializers.products import ProductMaterialSerializer
from workorder.tests.factories import (
    MaterialFactory,
    ProductFactory,
    PurchaseOrderItemFactory,
    PurchaseReceiveRecordFactory,
    SupplierFactory,
    UserFactory,
    WorkOrderFactory,
    WorkOrderMaterialFactory,
    WorkOrderProcessFactory,
)


@pytest.mark.django_db
class TestMaterialPlanning:
    def setup_method(self):
        self.user = UserFactory()
        self.supplier = SupplierFactory()
        self.requirement = MaterialFactory(
            name="150g双铜",
            specification_level="requirement",
            material_type="paper",
            paper_type="双铜",
            grammage=Decimal("150"),
            default_supplier=None,
        )
        self.stock_material = MaterialFactory(
            name="150g双铜大度",
            specification_level="stock",
            base_material=self.requirement,
            material_type="paper",
            paper_type="双铜",
            grammage=Decimal("150"),
            sheet_width_mm=Decimal("889"),
            sheet_height_mm=Decimal("1194"),
            stock_quantity=Decimal("100"),
            default_supplier=self.supplier,
        )
        self.work_order = WorkOrderFactory()
        self.wom = WorkOrderMaterialFactory(
            work_order=self.work_order,
            material=self.requirement,
            material_size="",
            material_usage="",
            need_cutting=True,
            planning_required=True,
            planning_status="draft",
        )

    def test_calculate_plan_converts_cut_size_to_parent_sheet_requirement(
        self,
    ):
        result = WorkOrderMaterialService.calculate_plan(
            wom=self.wom,
            purchase_material=self.stock_material,
            cut_width_mm=Decimal("443"),
            cut_height_mm=Decimal("595"),
            required_cut_quantity=Decimal("4000"),
            wastage_rate=Decimal("5"),
        )

        assert result.pieces_per_parent_sheet == 4
        assert result.theoretical_parent_quantity == Decimal("1000")
        assert result.planned_parent_quantity == Decimal("1050")
        assert result.purchase_quantity == Decimal("950")
        assert result.planning_status == "calculated"

    def test_calculate_plan_creates_hidden_job_specific_stock_specification(self):
        result = WorkOrderMaterialService.calculate_plan(
            wom=self.wom,
            purchase_material=None,
            custom_parent_width_mm=Decimal("920"),
            custom_parent_height_mm=Decimal("1250"),
            custom_supplier=self.supplier,
            custom_unit_price=Decimal("3.25"),
            cut_width_mm=Decimal("443"),
            cut_height_mm=Decimal("595"),
            required_cut_quantity=Decimal("4000"),
            wastage_rate=Decimal("5"),
        )

        custom = result.purchase_material
        assert custom is not None
        assert custom.is_temporary is True
        assert custom.is_active is True
        assert custom.base_material == self.requirement
        assert custom.temporary_for_work_order_material == self.wom
        assert custom.sheet_width_mm == Decimal("920")
        assert custom.sheet_height_mm == Decimal("1250")
        assert custom.default_supplier == self.supplier
        assert custom.unit_price == Decimal("3.25")
        assert result.parent_sheet_width_mm == Decimal("920")
        assert result.parent_sheet_height_mm == Decimal("1250")

    def test_recalculate_custom_plan_reuses_job_specific_stock_specification(self):
        first = WorkOrderMaterialService.calculate_plan(
            wom=self.wom,
            purchase_material=None,
            custom_parent_width_mm=Decimal("920"),
            custom_parent_height_mm=Decimal("1250"),
            custom_supplier=self.supplier,
            cut_width_mm=Decimal("443"),
            cut_height_mm=Decimal("595"),
            required_cut_quantity=Decimal("4000"),
        )
        custom_id = first.purchase_material_id

        second = WorkOrderMaterialService.calculate_plan(
            wom=self.wom,
            purchase_material=None,
            custom_parent_width_mm=Decimal("930"),
            custom_parent_height_mm=Decimal("1260"),
            custom_supplier=self.supplier,
            cut_width_mm=Decimal("443"),
            cut_height_mm=Decimal("595"),
            required_cut_quantity=Decimal("4000"),
        )

        assert second.purchase_material_id == custom_id
        assert second.purchase_material.sheet_width_mm == Decimal("930")
        assert second.purchase_material.sheet_height_mm == Decimal("1260")

    def test_job_specific_specification_flows_into_purchase_order(self):
        calculated = WorkOrderMaterialService.calculate_plan(
            wom=self.wom,
            purchase_material=None,
            custom_parent_width_mm=Decimal("920"),
            custom_parent_height_mm=Decimal("1250"),
            custom_supplier=self.supplier,
            custom_unit_price=Decimal("3.25"),
            cut_width_mm=Decimal("443"),
            cut_height_mm=Decimal("595"),
            required_cut_quantity=Decimal("4000"),
        )
        WorkOrderMaterialService.confirm_plan(wom=calculated, user=self.user)

        result = PurchaseOrderService.create_from_work_order(
            work_order_id=self.work_order.pk
        )

        assert result["created_item_count"] == 1
        purchase_order = result["purchase_orders"][0]
        item = self.work_order.purchase_orders.get(pk=purchase_order["id"]).items.get()
        assert item.material_id == calculated.purchase_material_id
        assert item.material.is_temporary is True
        assert item.material.sheet_width_mm == Decimal("920")
        assert item.material.sheet_height_mm == Decimal("1250")
        assert item.unit_price == Decimal("3.25")

        serializer = MaterialSerializer(
            item.material,
            data={"name": "不允许手工改名"},
            partial=True,
        )
        assert serializer.is_valid() is False
        assert "由物料规划维护" in str(serializer.errors)

    def test_product_material_auto_defers_non_paper_specification(self):
        rope_requirement = MaterialFactory(
            specification_level="requirement",
            material_type="packing",
            name="手挽绳要求",
        )
        serializer = ProductMaterialSerializer(
            data={
                "product": ProductFactory().pk,
                "material": rope_requirement.pk,
            }
        )

        assert serializer.is_valid(), serializer.errors
        item = serializer.save()
        assert item.calculation_mode == "specification_selection"
        assert item.preparation_mode == "pending"
        assert item.planning_required is True

    def test_product_material_auto_defers_paper_to_imposition(self):
        serializer = ProductMaterialSerializer(
            data={
                "product": ProductFactory().pk,
                "material": self.requirement.pk,
            }
        )

        assert serializer.is_valid(), serializer.errors
        item = serializer.save()
        assert item.calculation_mode == "sheet_imposition"
        assert item.preparation_mode == "pending"
        assert item.planning_required is True
        assert item.need_cutting is False

    def test_product_material_ignores_professional_mode_input(self):
        serializer = ProductMaterialSerializer(
            data={
                "product": ProductFactory().pk,
                "material": self.requirement.pk,
                "calculation_mode": "sheet_imposition",
                "preparation_mode": "direct",
            }
        )

        assert serializer.is_valid(), serializer.errors
        item = serializer.save()
        assert item.calculation_mode == "sheet_imposition"
        assert item.preparation_mode == "pending"

    def test_legacy_planning_flags_map_to_supplier_cutting(self):
        serializer = ProductMaterialSerializer(
            data={
                "product": ProductFactory().pk,
                "material": self.requirement.pk,
                "planning_required": True,
                "need_cutting": False,
            }
        )

        assert serializer.is_valid(), serializer.errors
        item = serializer.save()
        assert item.calculation_mode == "sheet_imposition"
        assert item.preparation_mode == "pending"

    def test_resolve_non_paper_requirement_selects_concrete_specification(self):
        rope_requirement = MaterialFactory(
            specification_level="requirement",
            material_type="packing",
            name="手挽绳",
            unit="条",
        )
        rope_stock = MaterialFactory(
            specification_level="stock",
            base_material=rope_requirement,
            material_type="packing",
            name="手挽绳 6mm 红色 40cm",
            specification="6mm/红色/40cm",
            unit="条",
            stock_quantity=Decimal("100"),
            default_supplier=self.supplier,
        )
        rope_plan = WorkOrderMaterialFactory(
            work_order=self.work_order,
            material=rope_requirement,
            calculation_mode="specification_selection",
            preparation_mode="pending",
            planning_required=True,
            planning_status="draft",
        )

        calculated = WorkOrderMaterialService.resolve_specification(
            wom=rope_plan,
            purchase_material=rope_stock,
            required_quantity=Decimal("300"),
        )
        confirmed = WorkOrderMaterialService.confirm_plan(
            wom=calculated,
            user=self.user,
        )

        rope_stock.refresh_from_db()
        assert confirmed.purchase_material == rope_stock
        assert confirmed.planned_material_quantity == Decimal("300")
        assert confirmed.reserved_quantity == Decimal("100")
        assert confirmed.purchase_quantity == Decimal("200")
        assert confirmed.preparation_mode == "direct"
        assert rope_stock.reserved_quantity == Decimal("100")

        rope_stock.stock_quantity = Decimal("300")
        rope_stock.save(update_fields=["stock_quantity"])
        WorkOrderMaterialService.allocate_received_inventory(
            material=rope_stock,
            quantity=Decimal("200"),
            preferred_wom=confirmed,
        )

        confirmed.refresh_from_db()
        rope_stock.refresh_from_db()
        assert confirmed.reserved_quantity == Decimal("300")
        assert confirmed.purchase_status == "received"
        assert rope_stock.reserved_quantity == Decimal("300")

    def test_calculate_plan_rejects_non_paper_legacy_planning(self):
        rope_requirement = MaterialFactory(
            specification_level="requirement",
            material_type="packing",
            name="手挽绳要求",
        )
        rope_plan = WorkOrderMaterialFactory(
            material=rope_requirement,
            planning_required=True,
            planning_status="draft",
            need_cutting=False,
        )
        rope_stock = MaterialFactory(
            specification_level="stock",
            base_material=rope_requirement,
            material_type="packing",
        )

        with pytest.raises(ServiceError, match="只有纸张类物料"):
            WorkOrderMaterialService.calculate_plan(
                wom=rope_plan,
                purchase_material=rope_stock,
                cut_width_mm=1,
                cut_height_mm=1,
                required_cut_quantity=1,
            )

    def test_resolve_specification_api_returns_calculated_plan(self):
        rope_requirement = MaterialFactory(
            specification_level="requirement",
            material_type="packing",
            unit="条",
        )
        rope_stock = MaterialFactory(
            specification_level="stock",
            base_material=rope_requirement,
            material_type="packing",
            unit="条",
        )
        rope_plan = WorkOrderMaterialFactory(
            material=rope_requirement,
            calculation_mode="specification_selection",
            preparation_mode="pending",
            planning_required=True,
            planning_status="draft",
        )
        admin = UserFactory(is_staff=True, is_superuser=True)
        client = APIClient()
        client.force_authenticate(admin)

        response = client.post(
            f"/api/v1/workorder-materials/{rope_plan.id}/resolve_specification/",
            {
                "purchase_material": rope_stock.id,
                "required_quantity": "300",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["planning_status"] == "calculated"
        assert response.json()["data"]["planned_material_quantity"] == "300.000"

    def test_supplier_cutting_does_not_generate_internal_cutting_task(self):
        process = WorkOrderProcessFactory(
            work_order=self.work_order,
            process__code="CUT",
            tasks=0,
        )
        self.wom.calculation_mode = "sheet_imposition"
        self.wom.preparation_mode = "supplier_cutting"
        self.wom.planning_required = True
        self.wom.need_cutting = False
        self.wom.planning_status = "confirmed"
        self.wom.planned_parent_quantity = 100
        self.wom.purchase_material = self.stock_material
        self.wom.save()

        tasks = TaskGenerationService.build_task_objects(process)

        assert tasks == []

    def test_confirm_plan_reserves_available_inventory_atomically(self):
        WorkOrderMaterialService.calculate_plan(
            wom=self.wom,
            purchase_material=self.stock_material,
            cut_width_mm=Decimal("443"),
            cut_height_mm=Decimal("595"),
            required_cut_quantity=Decimal("4000"),
            wastage_rate=Decimal("5"),
        )

        confirmed = WorkOrderMaterialService.confirm_plan(wom=self.wom, user=self.user)

        self.stock_material.refresh_from_db()
        assert confirmed.planning_status == "confirmed"
        assert confirmed.reserved_quantity == Decimal("100")
        assert confirmed.purchase_quantity == Decimal("950")
        assert self.stock_material.reserved_quantity == Decimal("100")

    def test_inbound_quantity_is_allocated_once_across_work_orders(self):
        self.stock_material.stock_quantity = 0
        self.stock_material.save(update_fields=["stock_quantity"])
        PurchaseOrderItemFactory(
            material=self.stock_material,
            quantity=Decimal("500"),
            received_quantity=0,
            purchase_order__status="ordered",
        )
        second_wom = WorkOrderMaterialFactory(
            material=self.requirement,
            planning_required=True,
            planning_status="draft",
        )

        for wom in (self.wom, second_wom):
            WorkOrderMaterialService.calculate_plan(
                wom=wom,
                purchase_material=self.stock_material,
                cut_width_mm=Decimal("443"),
                cut_height_mm=Decimal("595"),
                required_cut_quantity=Decimal("1600"),
                wastage_rate=0,
            )

        first = WorkOrderMaterialService.confirm_plan(wom=self.wom, user=self.user)
        second = WorkOrderMaterialService.confirm_plan(wom=second_wom, user=self.user)

        assert first.inbound_quantity_snapshot == Decimal("400")
        assert first.purchase_quantity == 0
        assert first.purchase_status == "ordered"
        assert second.inbound_quantity_snapshot == Decimal("100")
        assert second.purchase_quantity == Decimal("300")
        assert second.purchase_status == "pending"

    def test_qualified_receipt_converts_inbound_allocation_to_reservation(self):
        self.stock_material.stock_quantity = 0
        self.stock_material.save(update_fields=["stock_quantity"])
        inbound_item = PurchaseOrderItemFactory(
            material=self.stock_material,
            quantity=Decimal("500"),
            received_quantity=0,
            purchase_order__status="ordered",
        )
        WorkOrderMaterialService.calculate_plan(
            wom=self.wom,
            purchase_material=self.stock_material,
            cut_width_mm=Decimal("443"),
            cut_height_mm=Decimal("595"),
            required_cut_quantity=Decimal("1600"),
            wastage_rate=0,
        )
        WorkOrderMaterialService.confirm_plan(wom=self.wom, user=self.user)
        receipt = PurchaseReceiveRecordFactory(
            purchase_order_item=inbound_item,
            received_quantity=Decimal("400"),
            qualified_quantity=Decimal("400"),
            inspection_status="qualified",
        )

        assert receipt.stock_in(user=self.user) is True

        self.wom.refresh_from_db()
        self.stock_material.refresh_from_db()
        assert self.wom.inbound_quantity_snapshot == 0
        assert self.wom.reserved_quantity == Decimal("400")
        assert self.wom.purchase_status == "received"
        assert self.stock_material.stock_quantity == Decimal("400")
        assert self.stock_material.reserved_quantity == Decimal("400")

    def test_recalculation_of_confirmed_plan_requires_invalidation(self):
        WorkOrderMaterialService.calculate_plan(
            wom=self.wom,
            purchase_material=self.stock_material,
            cut_width_mm=Decimal("443"),
            cut_height_mm=Decimal("595"),
            required_cut_quantity=Decimal("4000"),
            wastage_rate=Decimal("5"),
        )
        WorkOrderMaterialService.confirm_plan(wom=self.wom, user=self.user)

        with pytest.raises(ServiceError, match="先作废"):
            WorkOrderMaterialService.calculate_plan(
                wom=self.wom,
                purchase_material=self.stock_material,
                cut_width_mm=Decimal("443"),
                cut_height_mm=Decimal("595"),
                required_cut_quantity=Decimal("4000"),
                wastage_rate=Decimal("6"),
            )

    def test_calculate_rejects_stock_sku_from_another_requirement(self):
        another_requirement = MaterialFactory(
            specification_level="requirement",
            material_type="paper",
        )
        wrong_stock = MaterialFactory(
            specification_level="stock",
            base_material=another_requirement,
            material_type="paper",
            sheet_width_mm=Decimal("889"),
            sheet_height_mm=Decimal("1194"),
        )

        with pytest.raises(ServiceError, match="不属于当前材料要求"):
            WorkOrderMaterialService.calculate_plan(
                wom=self.wom,
                purchase_material=wrong_stock,
                cut_width_mm=Decimal("443"),
                cut_height_mm=Decimal("595"),
                required_cut_quantity=Decimal("4000"),
                wastage_rate=Decimal("5"),
            )

    def test_purchase_order_rejects_unconfirmed_planning_material(self):
        result = PurchaseOrderService.create_from_work_order(
            work_order_id=self.work_order.id
        )

        assert result["total_count"] == 0
        assert result["blocked_item_count"] == 1
        assert result["blocked_items"][0]["reason"] == "物料规格计划尚未确认"

    def test_purchase_order_uses_selected_stock_sku_and_shortage(self):
        WorkOrderMaterialService.calculate_plan(
            wom=self.wom,
            purchase_material=self.stock_material,
            cut_width_mm=Decimal("443"),
            cut_height_mm=Decimal("595"),
            required_cut_quantity=Decimal("4000"),
            wastage_rate=Decimal("5"),
        )
        WorkOrderMaterialService.confirm_plan(wom=self.wom, user=self.user)

        result = PurchaseOrderService.create_from_work_order(
            work_order_id=self.work_order.id
        )

        assert result["created_item_count"] == 1
        item = self.wom.purchaseorderitem_set.get()
        assert item.material == self.stock_material
        assert item.quantity == Decimal("950")

    def test_invalidate_releases_reservation(self):
        WorkOrderMaterialService.calculate_plan(
            wom=self.wom,
            purchase_material=self.stock_material,
            cut_width_mm=Decimal("443"),
            cut_height_mm=Decimal("595"),
            required_cut_quantity=Decimal("4000"),
            wastage_rate=Decimal("5"),
        )
        WorkOrderMaterialService.confirm_plan(wom=self.wom, user=self.user)

        invalidated = WorkOrderMaterialService.invalidate_plan(
            wom=self.wom,
            user=self.user,
            reason="拼版尺寸变更",
        )

        self.stock_material.refresh_from_db()
        assert invalidated.planning_status == "invalidated"
        assert invalidated.reserved_quantity == 0
        assert self.stock_material.reserved_quantity == 0

    def test_material_plan_api_calculates_and_confirms(self):
        admin = UserFactory(is_staff=True, is_superuser=True)
        client = APIClient()
        client.force_authenticate(admin)

        calculate_response = client.post(
            f"/api/v1/workorder-materials/{self.wom.id}/calculate_plan/",
            {
                "purchase_material": self.stock_material.id,
                "cut_width_mm": "443",
                "cut_height_mm": "595",
                "required_cut_quantity": "4000",
                "wastage_rate": "5",
            },
            format="json",
        )
        assert calculate_response.status_code == status.HTTP_200_OK
        assert calculate_response.json()["data"]["pieces_per_parent_sheet"] == 4

        confirm_response = client.post(
            f"/api/v1/workorder-materials/{self.wom.id}/confirm_plan/"
        )
        assert confirm_response.status_code == status.HTTP_200_OK
        assert confirm_response.json()["data"]["planning_status"] == "confirmed"

    def test_material_plan_api_requires_authentication(self):
        response = APIClient().post(
            f"/api/v1/workorder-materials/{self.wom.id}/confirm_plan/"
        )

        assert response.status_code in {
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        }

    def test_material_plan_api_rejects_excessive_wastage(self):
        admin = UserFactory(is_staff=True, is_superuser=True)
        client = APIClient()
        client.force_authenticate(admin)

        response = client.post(
            f"/api/v1/workorder-materials/{self.wom.id}/calculate_plan/",
            {
                "purchase_material": self.stock_material.id,
                "cut_width_mm": "443",
                "cut_height_mm": "595",
                "required_cut_quantity": "4000",
                "wastage_rate": "101",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_work_order_edit_preserves_confirmed_plan_and_reservation(self):
        WorkOrderMaterialService.calculate_plan(
            wom=self.wom,
            purchase_material=self.stock_material,
            cut_width_mm=Decimal("443"),
            cut_height_mm=Decimal("595"),
            required_cut_quantity=Decimal("4000"),
            wastage_rate=Decimal("5"),
        )
        WorkOrderMaterialService.confirm_plan(wom=self.wom, user=self.user)
        serializer = WorkOrderCreateUpdateSerializer(
            self.work_order,
            data={
                "materials_data": [
                    {
                        "material": self.requirement.id,
                        "material_size": "客户端旧值",
                        "material_usage": "客户端旧值",
                        "need_cutting": True,
                        "planning_required": True,
                        "notes": "保留计划",
                    }
                ]
            },
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.wom.refresh_from_db()
        self.stock_material.refresh_from_db()
        assert self.wom.planning_status == "confirmed"
        assert self.wom.planned_parent_quantity == Decimal("1050")
        assert self.wom.material_usage != "客户端旧值"
        assert self.stock_material.reserved_quantity == Decimal("100")

    def test_work_order_edit_cannot_remove_confirmed_plan(self):
        WorkOrderMaterialService.calculate_plan(
            wom=self.wom,
            purchase_material=self.stock_material,
            cut_width_mm=Decimal("443"),
            cut_height_mm=Decimal("595"),
            required_cut_quantity=Decimal("4000"),
            wastage_rate=Decimal("5"),
        )
        WorkOrderMaterialService.confirm_plan(wom=self.wom, user=self.user)
        serializer = WorkOrderCreateUpdateSerializer(
            self.work_order,
            data={"materials_data": []},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        with pytest.raises(drf_serializers.ValidationError, match="不能直接删除"):
            serializer.save()


@pytest.mark.django_db
def test_work_order_material_defaults_keep_legacy_flow_compatible():
    wom = WorkOrderMaterialFactory()

    assert wom.planning_required is False
    assert wom.planning_status == WorkOrderMaterial.PlanningStatus.NOT_REQUIRED
