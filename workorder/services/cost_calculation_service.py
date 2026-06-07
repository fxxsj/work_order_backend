"""
成本核算服务

施工单完成后自动生成成本核算草稿，
统一封装材料成本、人工成本、设备成本的自动计算逻辑。
"""

import logging
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)


class CostCalculationService:
    """成本核算服务"""

    @staticmethod
    def generate_cost_draft(work_order):
        """
        为施工单生成成本核算草稿。

        计算逻辑：
        - 若 ProductionCost 不存在，则新建。
        - 自动调用 material_cost / labor_cost 的计算方法。
        - 最后汇总 total_cost。

        Args:
            work_order: WorkOrder 实例（状态应为 completed）

        Returns:
            ProductionCost: 成本记录对象
            bool: 是否为新建
        """
        from workorder.models.finance import ProductionCost

        cost, created = ProductionCost.objects.get_or_create(
            work_order=work_order,
            defaults={
                "period": timezone.now().strftime("%Y-%m"),
                "standard_cost": Decimal("0"),
            },
        )

        # 重新计算材料成本（无论是否新建，都确保数据最新）
        cost.auto_calculate_material_cost()

        # 重新计算人工和设备成本
        cost.auto_calculate_labor_cost()

        # 汇总总成本
        cost.calculate_total_cost()

        logger.info(
            f"施工单 {work_order.order_number} 成本核算草稿已{'新建' if created else '更新'}: "
            f"material={cost.material_cost}, labor={cost.labor_cost}, "
            f"equipment={cost.equipment_cost}, total={cost.total_cost}"
        )

        return cost, created
