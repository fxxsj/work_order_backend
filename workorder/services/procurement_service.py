"""
采购需求汇总与延迟预警服务。

提供施工单物料采购状态的全局视图：
- 按物料维度汇总采购需求（待采购/已下单/已到货）
- 采购延迟预警（对比施工单交货期与物料采购周期）
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List

from django.db.models import Count, Q, Sum
from django.utils import timezone

from workorder.constants.status import MaterialPurchaseStatus

logger = logging.getLogger(__name__)


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
                        "work_orders": [{"id": 1, "order_number": "WO...", "quantity": 100}],
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
        from workorder.models.materials import Material, PurchaseOrderItem

        # 查询所有活跃施工单的物料
        wo_materials = (
            WorkOrderMaterial.objects.filter(
                work_order__approval_status="approved",
                work_order__status__in=["pending", "in_progress"],
            )
            .select_related("material__default_supplier", "work_order")
            .order_by("material__name")
        )

        # 按物料分组汇总
        material_map: Dict[int, Dict[str, Any]] = {}

        for wom in wo_materials:
            mat = wom.material
            if mat.id not in material_map:
                material_map[mat.id] = {
                    "material_id": mat.id,
                    "material_name": mat.name,
                    "material_code": mat.code,
                    "material_unit": mat.unit,
                    "work_orders": [],
                    "total_required": 0,
                    "total_ordered": 0,
                    "total_received": 0,
                    "lead_time_days": mat.lead_time_days or 7,
                    "default_supplier_id": (
                        mat.default_supplier.id if mat.default_supplier else None
                    ),
                    "default_supplier_name": (
                        mat.default_supplier.name if mat.default_supplier else None
                    ),
                }

            item = material_map[mat.id]
            # 解析物料用量
            qty = _parse_material_usage(wom.material_usage)

            # 累计 work_order 信息（含需求量）
            existing_wo = next(
                (w for w in item["work_orders"] if w["id"] == wom.work_order_id),
                None
            )
            if existing_wo:
                existing_wo["quantity"] += qty
            else:
                item["work_orders"].append(
                    {
                        "id": wom.work_order_id,
                        "order_number": wom.work_order.order_number,
                        "quantity": qty,
                    }
                )

            item["total_required"] += qty

            # 根据采购状态累计
            if wom.purchase_status == MaterialPurchaseStatus.PENDING:
                pass  # 待采购，已计入 total_required
            elif wom.purchase_status == MaterialPurchaseStatus.ORDERED:
                item["total_ordered"] += qty
            elif wom.purchase_status in [
                MaterialPurchaseStatus.RECEIVED,
                MaterialPurchaseStatus.CUT,
                MaterialPurchaseStatus.COMPLETED,
            ]:
                item["total_received"] += qty

        # 计算汇总统计
        pending_count = sum(
            1 for v in material_map.values() if v["total_ordered"] == 0 and v["total_received"] == 0
        )
        ordered_count = sum(
            1 for v in material_map.values()
            if v["total_ordered"] > 0 and v["total_received"] == 0
        )
        received_count = sum(1 for v in material_map.values() if v["total_received"] > 0)

        # 确定每个物料的聚合状态
        for item in material_map.values():
            if item["total_received"] >= item["total_required"]:
                item["status"] = "received"
            elif item["total_ordered"] >= item["total_required"]:
                item["status"] = "ordered"
            elif item["total_ordered"] > 0:
                item["status"] = "partial_ordered"
            else:
                item["status"] = "pending"

        return {
            "summary": {
                "pending_count": pending_count,
                "ordered_count": ordered_count,
                "received_count": received_count,
                "total_materials": len(material_map),
            },
            "items": list(material_map.values()),
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
            .select_related("material__default_supplier", "work_order")
        )

        for wom in wo_materials:
            delivery_date = wom.work_order.delivery_date
            if not delivery_date:
                continue

            # 计算预计到货日
            lead_time = wom.material.lead_time_days or 7

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
                        "material_name": wom.material.name,
                        "material_code": wom.material.code,
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


def _parse_material_usage(usage_str: str) -> int:
    """解析物料用量字符串，提取数字部分"""
    import re

    if not usage_str:
        return 0
    numbers = re.findall(r"\d+\.?\d*", usage_str)
    if numbers:
        try:
            return int(float(numbers[0]))
        except (ValueError, IndexError):
            return 0
    return 0