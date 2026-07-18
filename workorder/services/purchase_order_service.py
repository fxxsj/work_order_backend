"""采购单业务服务"""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from rest_framework import status

from workorder.constants.status import MaterialPurchaseStatus
from workorder.models.core import WorkOrder
from workorder.models.material_modes import requires_material_planning
from workorder.models.materials import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceiveRecord,
)
from workorder.services.service_errors import ServiceError
from workorder.services.procurement_rules import (
    get_procurement_material,
    get_purchase_requirement_quantity,
    get_supplier_context,
)


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
    @transaction.atomic
    def create_from_work_order(
        *,
        work_order_id,
        material_ids=None,
        work_order_material_ids=None,
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
            work_order = WorkOrder.objects.select_for_update().get(pk=work_order_id)
        except WorkOrder.DoesNotExist as exc:
            raise ServiceError("施工单不存在", code=status.HTTP_404_NOT_FOUND) from exc

        wo_materials = (
            work_order.materials.select_for_update()
            .select_related(
                "material",
                "material__default_supplier",
                "purchase_material",
                "purchase_material__default_supplier",
            )
            .prefetch_related(
                "material__materialsupplier_set__supplier",
                "purchase_material__materialsupplier_set__supplier",
            )
            .filter(purchase_status=MaterialPurchaseStatus.PENDING)
        )

        if material_ids:
            wo_materials = wo_materials.filter(
                Q(material_id__in=material_ids)
                | Q(purchase_material_id__in=material_ids)
            )
        if work_order_material_ids:
            wo_materials = wo_materials.filter(id__in=work_order_material_ids)

        if not wo_materials.exists():
            raise ServiceError("没有待采购的物料", code=status.HTTP_400_BAD_REQUEST)

        unconfirmed_plans = [
            wom
            for wom in wo_materials
            if requires_material_planning(wom)
            and wom.planning_status != wom.PlanningStatus.CONFIRMED
        ]
        blocked_items = []
        if unconfirmed_plans:
            blocked_items.extend(
                {
                    "work_order_material_id": wom.id,
                    "material_id": wom.material_id,
                    "material_name": wom.material.name,
                    "reason": "物料规格计划尚未确认",
                }
                for wom in unconfirmed_plans
            )
            wo_materials = wo_materials.exclude(
                id__in=[wom.id for wom in unconfirmed_plans]
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
                "blocked_item_count": len(blocked_items),
                "blocked_items": blocked_items,
            }

        no_shortage_ids = {
            wom.id
            for wom in wo_materials
            if requires_material_planning(wom) and wom.purchase_quantity <= 0
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

        supplier_contexts = {}
        missing_supplier = []
        for wom in wo_materials:
            procurement_material = get_procurement_material(wom)
            context = get_supplier_context(procurement_material)
            supplier_contexts[wom.id] = context
            if not context["supplier"]:
                missing_supplier.append(
                    {
                        "work_order_material_id": wom.id,
                        "material_id": wom.material_id,
                        "material_name": wom.material.name,
                        "procurement_material_id": procurement_material.id,
                        "procurement_material_name": procurement_material.name,
                        "reason": "具体采购规格未配置有效供应商",
                    }
                )

        if missing_supplier:
            blocked_items.extend(missing_supplier)
            wo_materials = wo_materials.exclude(
                id__in=[item["work_order_material_id"] for item in missing_supplier]
            )

        if not wo_materials.exists():
            return {
                "purchase_orders": [],
                "total_count": 0,
                "created_item_count": 0,
                "skipped_item_count": len(skipped_items),
                "skipped_items": skipped_items,
                "blocked_item_count": len(blocked_items),
                "blocked_items": blocked_items,
            }

        supplier_groups = {}
        for wom in wo_materials:
            supplier = supplier_contexts[wom.id]["supplier"]
            if supplier.id not in supplier_groups:
                supplier_groups[supplier.id] = {
                    "supplier": supplier,
                    "items": [],
                }
            supplier_groups[supplier.id]["items"].append(
                (wom, supplier_contexts[wom.id])
            )

        quantity_overrides = {}
        for item_override in item_overrides:
            wom_id = item_override.get("work_order_material_id")
            qty = item_override.get("quantity")
            if not wom_id or qty is None:
                continue
            try:
                quantity = Decimal(str(qty))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ServiceError(
                    "采购数量格式不正确",
                    code=status.HTTP_400_BAD_REQUEST,
                ) from exc
            if quantity <= 0:
                raise ServiceError(
                    "采购数量必须大于0",
                    code=status.HTTP_400_BAD_REQUEST,
                )
            quantity_overrides[wom_id] = quantity

        created_orders = []
        created_item_count = 0
        for group_data in supplier_groups.values():
            po = PurchaseOrder.objects.create(
                supplier=group_data["supplier"],
                work_order=work_order,
                notes=notes,
            )

            for wom, context in group_data["items"]:
                procurement_material = get_procurement_material(wom)
                default_quantity = get_purchase_requirement_quantity(wom)
                quantity = quantity_overrides.get(wom.id, default_quantity)
                if quantity <= 0:
                    raise ServiceError(
                        f"物料 {procurement_material.name} 的采购数量必须大于0",
                        code=status.HTTP_400_BAD_REQUEST,
                    )
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    material=procurement_material,
                    quantity=quantity,
                    unit_price=context["unit_price"],
                    supplier_code=context["supplier_code"],
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
            "blocked_item_count": len(blocked_items),
            "blocked_items": blocked_items,
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
