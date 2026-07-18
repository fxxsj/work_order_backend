"""
采购需求汇总与延迟预警服务。

提供施工单物料采购状态的全局视图：
- 按物料维度汇总采购需求（待采购/已下单/已到货）
- 采购延迟预警（对比施工单交货期与物料采购周期）
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from workorder.constants.status import MaterialPurchaseStatus
from workorder.models.material_modes import requires_material_planning
from workorder.services.procurement_rules import (
    get_planned_demand_quantity,
    get_procurement_material,
    get_purchase_requirement_quantity,
    get_supplier_context,
)


class ProcurementService:
    """采购需求汇总与预警服务"""

    @staticmethod
    def get_procurement_summary() -> Dict[str, Any]:
        """
        获取全局采购需求汇总。

        Returns:
            {
                "summary": {
                    "pending_count": N,    # 待采购物料数
                    "ordered_count": N,    # 已下单物料数
                    "received_count": N,   # 已到货物料数
                },
                "items": [
                    {
                        "material_id": 1,
                        "material_name": "...",
                        "material_code": "...",
                        "material_unit": "...",
                        "work_orders": [
                            {"id": 1, "order_number": "WO...",
                             "quantity": 100}
                        ],
                        "total_required": 100,
                        "total_ordered": 80,
                        "total_received": 0,
                        "status": "partial_ordered",
                        "lead_time_days": 7,
                        "default_supplier_id": 1,
                        "default_supplier_name": "...",
                    },
                    ...
                ]
            }
        """
        from workorder.models.core import WorkOrderMaterial

        # 查询所有活跃施工单的物料
        wo_materials = (
            WorkOrderMaterial.objects.filter(
                work_order__approval_status="approved",
                work_order__status__in=["pending", "in_progress"],
            )
            .select_related(
                "material__default_supplier",
                "purchase_material__default_supplier",
                "work_order",
            )
            .prefetch_related(
                "material__materialsupplier_set__supplier",
                "purchase_material__materialsupplier_set__supplier",
                "purchaseorderitem_set__purchase_order",
            )
            .order_by("material__name")
        )

        planning_pending_items = []
        # 按施工单确认后的具体库存/采购 SKU 分组汇总
        material_map: Dict[int, Dict[str, Any]] = {}

        for wom in wo_materials:
            if (
                requires_material_planning(wom)
                and wom.planning_status != wom.PlanningStatus.CONFIRMED
            ):
                planning_pending_items.append(
                    {
                        "work_order_material_id": wom.id,
                        "work_order_id": wom.work_order_id,
                        "work_order_number": wom.work_order.order_number,
                        "material_id": wom.material_id,
                        "material_name": wom.material.name,
                        "reason": "物料规格计划尚未确认",
                    }
                )
                continue

            mat = get_procurement_material(wom)
            supplier_context = get_supplier_context(mat)
            if mat.id not in material_map:
                material_map[mat.id] = {
                    "material_id": mat.id,
                    "material_name": mat.name,
                    "material_code": mat.code,
                    "material_unit": mat.unit,
                    "work_orders": [],
                    "total_required": 0,
                    "total_to_purchase": 0,
                    "total_draft": 0,
                    "total_ordered": 0,
                    "total_received": 0,
                    "lead_time_days": supplier_context["lead_time_days"],
                    "default_supplier_id": (
                        supplier_context["supplier"].id
                        if supplier_context["supplier"]
                        else None
                    ),
                    "default_supplier_name": (
                        supplier_context["supplier"].name
                        if supplier_context["supplier"]
                        else None
                    ),
                }

            item = material_map[mat.id]
            required_qty = get_planned_demand_quantity(wom)
            purchase_qty = get_purchase_requirement_quantity(wom)
            active_purchase_items = [
                purchase_item
                for purchase_item in wom.purchaseorderitem_set.all()
                if purchase_item.purchase_order.status != "cancelled"
            ]
            draft_qty = sum(
                (
                    Decimal(str(purchase_item.quantity))
                    for purchase_item in active_purchase_items
                    if purchase_item.purchase_order.status == "pending"
                ),
                Decimal("0"),
            )
            ordered_qty = sum(
                (
                    Decimal(str(purchase_item.quantity))
                    for purchase_item in active_purchase_items
                    if purchase_item.purchase_order.status in {"ordered", "received"}
                ),
                Decimal("0"),
            )
            received_qty = sum(
                (
                    Decimal(str(purchase_item.received_quantity or 0))
                    for purchase_item in active_purchase_items
                ),
                Decimal("0"),
            )

            # 累计 work_order 信息（含需求量）
            existing_wo = next(
                (w for w in item["work_orders"] if w["id"] == wom.work_order_id),
                None,
            )
            if existing_wo:
                existing_wo["quantity"] += required_qty
                existing_wo["purchase_quantity"] += purchase_qty
            else:
                item["work_orders"].append(
                    {
                        "id": wom.work_order_id,
                        "order_number": wom.work_order.order_number,
                        "quantity": required_qty,
                        "purchase_quantity": purchase_qty,
                    }
                )

            item["total_required"] += required_qty
            item["total_to_purchase"] += purchase_qty
            item["total_draft"] += draft_qty
            item["total_ordered"] += ordered_qty
            item["total_received"] += received_qty

        # 计算汇总统计
        pending_count = sum(
            1
            for v in material_map.values()
            if v["total_to_purchase"] > 0
            and v["total_draft"] == 0
            and v["total_ordered"] == 0
            and v["total_received"] == 0
        )
        draft_count = sum(1 for v in material_map.values() if v["total_draft"] > 0)
        ordered_count = sum(
            1
            for v in material_map.values()
            if v["total_ordered"] > 0 and v["total_received"] == 0
        )
        received_count = sum(
            1 for v in material_map.values() if v["total_received"] > 0
        )
        covered_count = sum(
            1 for v in material_map.values() if v["total_to_purchase"] <= 0
        )

        # 确定每个物料的聚合状态
        for item in material_map.values():
            target = item["total_to_purchase"]
            if target <= 0:
                item["status"] = "covered"
            elif item["total_received"] >= target:
                item["status"] = "received"
            elif item["total_ordered"] >= target:
                item["status"] = "ordered"
            elif item["total_ordered"] > 0:
                item["status"] = "partial_ordered"
            elif item["total_draft"] > 0:
                item["status"] = "pending_order"
            else:
                item["status"] = "pending"

        return {
            "summary": {
                "pending_count": pending_count,
                "draft_count": draft_count,
                "ordered_count": ordered_count,
                "received_count": received_count,
                "covered_count": covered_count,
                "planning_pending_count": len(planning_pending_items),
                "total_materials": len(material_map),
            },
            "items": list(material_map.values()),
            "planning_pending_items": planning_pending_items,
        }

    @staticmethod
    def get_delay_warnings() -> Dict[str, Any]:
        """
        获取采购延迟预警。

        对 purchase_status 为 pending/ordered 的施工单物料，
        计算预计到货日并与施工单交货日对比，超出则预警。

        Returns:
            {
                "warnings": [
                    {
                        "work_order_id": 1,
                        "work_order_number": "WO20260516-0001",
                        "delivery_date": "2026-05-25",
                        "material_name": "...",
                        "material_code": "...",
                        "purchase_status": "pending",
                        "estimated_arrival": "2026-05-23",
                        "delay_days": 2,
                        "severity": "low",
                    },
                    ...
                ]
            }
        """
        from workorder.models.core import WorkOrderMaterial

        today = date.today()
        warnings: List[Dict[str, Any]] = []

        # 仅查 pending 和 ordered 状态的物料
        wo_materials = (
            WorkOrderMaterial.objects.filter(
                purchase_status__in=[
                    MaterialPurchaseStatus.PENDING,
                    MaterialPurchaseStatus.ORDERED,
                ],
                work_order__approval_status="approved",
                work_order__status__in=["pending", "in_progress"],
            )
            .select_related(
                "material__default_supplier",
                "purchase_material__default_supplier",
                "work_order",
            )
            .prefetch_related(
                "material__materialsupplier_set__supplier",
                "purchase_material__materialsupplier_set__supplier",
            )
        )

        for wom in wo_materials:
            if (
                requires_material_planning(wom)
                and wom.planning_status != wom.PlanningStatus.CONFIRMED
            ):
                continue
            if get_purchase_requirement_quantity(wom) <= 0:
                continue
            delivery_date = wom.work_order.delivery_date
            if not delivery_date:
                continue

            material = get_procurement_material(wom)
            supplier_context = get_supplier_context(material)
            lead_time = supplier_context["lead_time_days"]

            if wom.purchase_status == MaterialPurchaseStatus.PENDING:
                # 还未下单，以今天为起点
                estimated_arrival = today + timedelta(days=lead_time)
            else:
                # 已下单但未到货，以 ordered_date 为起点
                if wom.purchase_date:
                    estimated_arrival = wom.purchase_date + timedelta(days=lead_time)
                else:
                    estimated_arrival = today + timedelta(days=lead_time)

            delay_days = (estimated_arrival - delivery_date).days

            if delay_days > 0:
                # 确定严重程度
                if delay_days <= 3:
                    severity = "low"
                elif delay_days <= 7:
                    severity = "medium"
                else:
                    severity = "high"

                warnings.append(
                    {
                        "work_order_id": wom.work_order_id,
                        "work_order_number": wom.work_order.order_number,
                        "delivery_date": delivery_date.isoformat(),
                        "material_name": material.name,
                        "material_code": material.code,
                        "requirement_material_name": wom.material.name,
                        "purchase_status": wom.purchase_status,
                        "estimated_arrival": estimated_arrival.isoformat(),
                        "delay_days": delay_days,
                        "severity": severity,
                        "lead_time_days": lead_time,
                    }
                )

        # 按 delay_days 降序排列
        warnings.sort(key=lambda w: w["delay_days"], reverse=True)

        return {"warnings": warnings, "total": len(warnings)}
