"""采购单业务服务"""

from django.db import transaction
from rest_framework import status

from workorder.constants.status import MaterialPurchaseStatus
from workorder.models.core import WorkOrder
from workorder.models.materials import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceiveRecord,
)
from workorder.services.service_errors import ServiceError
from workorder.services.task_generation import TaskGenerationService


class PurchaseOrderService:
    """采购单业务服务"""

    @staticmethod
    def receive_items(*, order, items_data: list, received_date, user):
        """分批收货，创建收货记录。

        Returns:
            dict: {"created_record_ids": [...], "errors": [...]}

        Raises:
            ServiceError: 采购单状态不满足时抛出
        """
        if order.status != "ordered":
            raise ServiceError(
                "只有已下单状态的采购单可以收货",
                code=status.HTTP_400_BAD_REQUEST,
            )

        created_records = []
        errors = []

        with transaction.atomic():
            for item_data in items_data:
                item_id = item_data.get("item_id")
                received_quantity = item_data.get("received_quantity")
                delivery_note_number = item_data.get("delivery_note_number", "")
                notes = item_data.get("notes", "")

                item = order.items.filter(id=item_id).first()
                if not item:
                    errors.append(f"采购单明细 {item_id} 不存在")
                    continue

                existing_received = sum(
                    r.received_quantity or 0 for r in item.receive_records.all()
                )
                remaining = item.quantity - existing_received

                if received_quantity > remaining:
                    errors.append(
                        f"物料 {item.material.name} 收货数量 {received_quantity} "
                        f"超过剩余数量 {remaining}"
                    )
                    continue

                record = PurchaseReceiveRecord.objects.create(
                    purchase_order_item=item,
                    received_quantity=received_quantity,
                    received_date=received_date,
                    received_by=user,
                    delivery_note_number=delivery_note_number,
                    notes=notes,
                    inspection_status="pending",
                )
                created_records.append(record.id)

        return {"created_record_ids": created_records, "errors": errors}

    @staticmethod
    def create_from_work_order(
        *,
        work_order_id,
        material_ids=None,
        notes: str = "",
        item_overrides: list = None,
    ):
        """从施工单创建采购单。

        按物料默认供应商自动分组，每组生成一个采购单。

        Returns:
            dict: 包含 created_orders、created_item_count、
                skipped_items、blocked_items

        Raises:
            ServiceError: 参数缺失或业务规则不满足时抛出
        """
        item_overrides = item_overrides or []

        if not work_order_id:
            raise ServiceError(
                "缺少 work_order_id 参数", code=status.HTTP_400_BAD_REQUEST
            )

        try:
            work_order = WorkOrder.objects.get(pk=work_order_id)
        except WorkOrder.DoesNotExist as exc:
            raise ServiceError("施工单不存在", code=status.HTTP_404_NOT_FOUND) from exc

        wo_materials = work_order.materials.select_related(
            "material",
            "material__default_supplier",
            "purchase_material",
            "purchase_material__default_supplier",
        ).filter(purchase_status=MaterialPurchaseStatus.PENDING)

        if material_ids:
            wo_materials = wo_materials.filter(material_id__in=material_ids)

        if not wo_materials.exists():
            raise ServiceError("没有待采购的物料", code=status.HTTP_400_BAD_REQUEST)

        unconfirmed_plans = [
            wom
            for wom in wo_materials
            if wom.planning_required
            and wom.planning_status != wom.PlanningStatus.CONFIRMED
        ]
        if unconfirmed_plans:
            names = "、".join(item.material.name for item in unconfirmed_plans)
            raise ServiceError(
                f"物料计划尚未确认：{names}",
                code=status.HTTP_409_CONFLICT,
            )

        existing_item_wom_ids = set(
            PurchaseOrderItem.objects.filter(
                work_order_material__in=wo_materials,
            )
            .exclude(purchase_order__status="cancelled")
            .values_list("work_order_material_id", flat=True)
        )
        skipped_items = []
        if existing_item_wom_ids:
            skipped_items = [
                {
                    "work_order_material_id": wom.id,
                    "material_id": wom.material_id,
                    "material_name": wom.material.name,
                    "reason": "已存在未取消的关联采购单明细",
                }
                for wom in wo_materials
                if wom.id in existing_item_wom_ids
            ]
            wo_materials = wo_materials.exclude(id__in=existing_item_wom_ids)

        if not wo_materials.exists():
            return {
                "purchase_orders": [],
                "total_count": 0,
                "created_item_count": 0,
                "skipped_item_count": len(skipped_items),
                "skipped_items": skipped_items,
                "blocked_items": [],
            }

        no_shortage_ids = {
            wom.id
            for wom in wo_materials
            if wom.planning_required and wom.purchase_quantity <= 0
        }
        if no_shortage_ids:
            skipped_items.extend(
                {
                    "work_order_material_id": wom.id,
                    "material_id": wom.material_id,
                    "material_name": wom.material.name,
                    "reason": "库存和在途数量已覆盖计划需求",
                }
                for wom in wo_materials
                if wom.id in no_shortage_ids
            )
            wo_materials = wo_materials.exclude(id__in=no_shortage_ids)

        missing_supplier = []
        for wom in wo_materials:
            procurement_material = wom.purchase_material or wom.material
            if not procurement_material.default_supplier:
                missing_supplier.append(
                    {
                        "work_order_material_id": wom.id,
                        "material_id": wom.material_id,
                        "material_name": wom.material.name,
                        "reason": "物料未配置默认供应商",
                    }
                )

        if missing_supplier:
            raise ServiceError(
                "部分物料没有默认供应商，请先配置",
                code=status.HTTP_400_BAD_REQUEST,
                data={"blocked_items": missing_supplier},
            )

        supplier_groups = {}
        for wom in wo_materials:
            procurement_material = wom.purchase_material or wom.material
            supplier = procurement_material.default_supplier
            if supplier.id not in supplier_groups:
                supplier_groups[supplier.id] = {
                    "supplier": supplier,
                    "items": [],
                }
            supplier_groups[supplier.id]["items"].append(wom)

        quantity_overrides = {}
        for item_override in item_overrides:
            wom_id = item_override.get("work_order_material_id")
            qty = item_override.get("quantity")
            if wom_id and qty:
                quantity_overrides[wom_id] = qty

        created_orders = []
        created_item_count = 0
        with transaction.atomic():
            for group_data in supplier_groups.values():
                po = PurchaseOrder.objects.create(
                    supplier=group_data["supplier"],
                    work_order=work_order,
                    notes=notes,
                )

                for wom in group_data["items"]:
                    procurement_material = wom.purchase_material or wom.material
                    default_quantity = (
                        wom.purchase_quantity
                        if wom.planning_required
                        else TaskGenerationService._parse_material_usage(
                            wom.material_usage or ""
                        )
                        or 1
                    )
                    quantity = quantity_overrides.get(wom.id, default_quantity)
                    PurchaseOrderItem.objects.create(
                        purchase_order=po,
                        material=procurement_material,
                        quantity=quantity,
                        unit_price=procurement_material.unit_price or 0,
                        work_order_material=wom,
                    )
                    created_item_count += 1

                po.update_total_amount()
                created_orders.append(po)

        result = []
        for po in created_orders:
            po = PurchaseOrder.objects.select_related("supplier").get(pk=po.id)
            result.append(
                {
                    "id": po.id,
                    "order_number": po.order_number,
                    "supplier_name": po.supplier.name,
                    "total_amount": str(po.total_amount),
                    "items_count": po.items.count(),
                }
            )

        return {
            "purchase_orders": result,
            "total_count": len(result),
            "created_item_count": created_item_count,
            "skipped_item_count": len(skipped_items),
            "skipped_items": skipped_items,
            "blocked_items": [],
        }

    @staticmethod
    @transaction.atomic
    def cancel(*, order):
        """取消采购单。"""
        if order.status in ["received", "cancelled"]:
            raise ServiceError(
                "已收货或已取消的采购单无法取消",
                code=status.HTTP_400_BAD_REQUEST,
            )
        linked_material_ids = list(
            order.items.exclude(work_order_material__isnull=True).values_list(
                "work_order_material_id", flat=True
            )
        )
        order.status = "cancelled"
        order.save(update_fields=["status"])
        if linked_material_ids:
            from workorder.models.core import WorkOrderMaterial

            for wom in WorkOrderMaterial.objects.select_for_update().filter(
                id__in=linked_material_ids
            ):
                has_other_active_order = (
                    PurchaseOrderItem.objects.filter(
                        work_order_material=wom,
                    )
                    .exclude(purchase_order__status="cancelled")
                    .exists()
                )
                if not has_other_active_order:
                    wom.purchase_status = MaterialPurchaseStatus.PENDING
                    wom.purchase_date = None
                    wom.save(update_fields=["purchase_status", "purchase_date"])
        return order
