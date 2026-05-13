"""
物料/资产确认触发服务。

当物料状态或版型确认状态变化时，自动更新相关任务的完成数量。
所有逻辑集中在此处，避免散落在 signals.py 中。
"""

import re
from django.db import transaction

from workorder.constants.status import TaskStatus
from workorder.models import WorkOrderTask


def parse_material_usage(usage_str: str) -> int:
    """
    解析物料用量字符串，提取数字部分。

    Args:
        usage_str: 物料用量字符串，如 "2.5mm" / "100张"

    Returns:
        int: 提取到的第一个数字，解析失败返回 0
    """
    if not usage_str:
        return 0
    numbers = re.findall(r"\d+", usage_str)
    if numbers:
        return int(numbers[0])
    return 0


def update_cutting_tasks_on_material_cut(material_instance) -> None:
    """
    物料状态变为'cut'（已开料）时，自动更新相关开料任务的完成数量。

    Args:
        material_instance: WorkOrderMaterial 实例
    """
    quantity = parse_material_usage(material_instance.material_usage)
    if quantity <= 0:
        return

    with transaction.atomic():
        cutting_tasks = (
            WorkOrderTask.objects.select_for_update()
            .filter(
                task_type="cutting",
                material=material_instance.material,
                work_order_process__work_order=material_instance.work_order,
                auto_calculate_quantity=True,
                status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS],
            )
        )
        for task in cutting_tasks:
            task.quantity_completed = quantity
            if task.production_quantity and quantity >= task.production_quantity:
                task.status = TaskStatus.COMPLETED
            elif task.status == TaskStatus.PENDING:
                task.status = TaskStatus.IN_PROGRESS
            task.save(update_fields=["quantity_completed", "status"])
            if task.status == TaskStatus.COMPLETED:
                task.work_order_process.check_and_update_status()


def complete_plate_tasks(
    artwork=None,
    die=None,
    foiling_plate=None,
    embossing_plate=None,
) -> None:
    """
    资产（ Artwork/Die/FoilingPlate/EmbossingPlate）确认时，
    自动完成相关制版任务。

    只处理从"未确认"变为"已确认"的情况，由调用方确保前提条件。
    """
    filters = {"task_type": "plate_making", "auto_calculate_quantity": True, "status__in": [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]}
    # 只填充非 None 的参数
    if artwork is not None:
        filters["artwork"] = artwork
    if die is not None:
        filters["die"] = die
    if foiling_plate is not None:
        filters["foiling_plate"] = foiling_plate
    if embossing_plate is not None:
        filters["embossing_plate"] = embossing_plate

    with transaction.atomic():
        plate_tasks = WorkOrderTask.objects.select_for_update().filter(**filters)
        for task in plate_tasks:
            if task.quantity_completed < 1:
                task.quantity_completed = 1
                task.status = TaskStatus.COMPLETED
                task.save(update_fields=["quantity_completed", "status"])
                task.work_order_process.check_and_update_status()
