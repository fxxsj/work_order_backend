"""施工单物料进入采购阶段后的统一解析规则。"""

import re
from decimal import Decimal, InvalidOperation

from workorder.models.material_modes import (
    requires_material_planning,
    requires_specification_selection,
)


def parse_material_quantity(value) -> Decimal:
    """从历史用量文本中提取数量，保留小数精度。"""
    if value is None:
        return Decimal("0")
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    if not match:
        return Decimal("0")
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return Decimal("0")


def get_procurement_material(work_order_material):
    """返回实际库存/采购 SKU；未规划时暂时回退材料要求。"""
    return work_order_material.purchase_material or work_order_material.material


def get_planned_demand_quantity(work_order_material) -> Decimal:
    """返回本单完整物料需求量，不等同于需要采购的缺口。"""
    if requires_specification_selection(work_order_material):
        return Decimal(str(work_order_material.planned_material_quantity or 0))
    if requires_material_planning(work_order_material):
        return Decimal(str(work_order_material.planned_parent_quantity or 0))
    return parse_material_quantity(work_order_material.material_usage)


def get_purchase_requirement_quantity(work_order_material) -> Decimal:
    """返回扣除库存预留和在途后的实际采购数量。"""
    if requires_material_planning(work_order_material):
        return Decimal(str(work_order_material.purchase_quantity or 0))
    return get_planned_demand_quantity(work_order_material)


def has_active_purchase_order(work_order_material) -> bool:
    """判断施工单物料是否已有未取消的采购明细。"""
    prefetched = getattr(work_order_material, "_prefetched_objects_cache", {}).get(
        "purchaseorderitem_set"
    )
    if prefetched is not None:
        return any(item.purchase_order.status != "cancelled" for item in prefetched)
    return work_order_material.purchaseorderitem_set.exclude(
        purchase_order__status="cancelled"
    ).exists()


def get_supplier_context(material):
    """解析 SKU 的有效供应商、供应商价、采购周期和起订量。"""
    prefetched = getattr(material, "_prefetched_objects_cache", {}).get(
        "materialsupplier_set"
    )
    if prefetched is None:
        active_relations = list(
            material.materialsupplier_set.select_related("supplier").filter(
                supplier__status="active"
            )
        )
    else:
        active_relations = [
            item for item in prefetched if item.supplier.status == "active"
        ]
    default_supplier = material.default_supplier
    relation = None
    supplier = None

    if default_supplier and default_supplier.status == "active":
        supplier = default_supplier
        relation = next(
            (
                item
                for item in active_relations
                if item.supplier_id == default_supplier.id
            ),
            None,
        )
    else:
        relation = next(
            iter(
                sorted(
                    active_relations,
                    key=lambda item: (not item.is_preferred, item.id),
                )
            ),
            None,
        )
        if relation:
            supplier = relation.supplier

    return {
        "supplier": supplier,
        "supplier_relation": relation,
        "unit_price": (
            relation.supplier_price
            if relation is not None
            else Decimal(str(material.unit_price or 0))
        ),
        "supplier_code": relation.supplier_code if relation is not None else "",
        "min_order_quantity": (
            relation.min_order_quantity if relation is not None else Decimal("0")
        ),
        "lead_time_days": (
            relation.lead_time_days
            if relation is not None
            else (material.lead_time_days or 7)
        ),
    }
