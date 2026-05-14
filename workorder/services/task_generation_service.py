"""
任务生成服务 (Task Generation Service)

从 models/core.py 的 WorkOrderProcess.generate_tasks() 迁移而来。
提供工序任务生成的业务逻辑，与 TaskGenerationService（旧 task_generation.py）配合使用。

主要功能：
- 根据工序类型（CTP/CUT/PRT/FOIL_G/EMB/DIE/PACK）生成对应任务
- 支持图稿、刀模、烫金版、压凸版、物料、产品等关联对象
- 解析物料用量字符串
"""
import re
from django.db import transaction

from workorder.constants.status import TaskStatus, TaskType


class TaskGenerationService:
    """工序任务生成服务

    提供基于工序类型生成任务的业务逻辑，替代 models/core.py 中的 generate_tasks()。
    """

    # 工序代码常量（与 ProcessCodes 对应）
    CTP = "CTP"
    CUT = "CUT"
    PRT = "PRT"
    FOIL_G = "FOIL_G"
    EMB = "EMB"
    DIE = "DIE"
    PACK = "PACK"

    @staticmethod
    def generate_tasks_for_process(work_order_process):
        """为单个工序生成任务并分派

        Args:
            work_order_process: WorkOrderProcess 实例

        Returns:
            list: 生成的任务列表
        """
        from ..models import WorkOrderTask

        # 如果已经有任务，不再生成
        if work_order_process.tasks.exists():
            return []

        tasks = TaskGenerationService.build_task_objects(work_order_process)
        created_tasks = []

        for task in tasks:
            task.save()
            work_order_process._auto_assign_task(task)
            created_tasks.append(task)

        return created_tasks

    @staticmethod
    def build_task_objects(work_order_process):
        """为工序构建任务对象列表（不保存到数据库）

        Args:
            work_order_process: WorkOrderProcess 实例

        Returns:
            list: 未保存的 WorkOrderTask 对象列表
        """
        from ..models import WorkOrderTask
        from ..models.process_codes import ProcessCodes

        process = work_order_process.process
        work_order = work_order_process.work_order
        process_code = process.code
        order_number = work_order.order_number
        production_quantity = work_order.production_quantity or 0

        tasks = []

        if process_code == ProcessCodes.CTP:
            # 制版工序：为图稿、刀模、烫金版、压凸版每个生成一个任务
            for artwork in work_order.artworks.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type=TaskType.PLATE_MAKING,
                    artwork=artwork,
                    work_content=f"{order_number}制版审核",
                    production_quantity=1,
                    quantity_completed=0,
                    status=TaskStatus.PENDING,
                    auto_calculate_quantity=True,
                ))
            for die in work_order.dies.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type=TaskType.PLATE_MAKING,
                    die=die,
                    work_content=f"{order_number}制版审核",
                    production_quantity=1,
                    quantity_completed=0,
                    status=TaskStatus.PENDING,
                    auto_calculate_quantity=True,
                ))
            for foiling_plate in work_order.foiling_plates.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type=TaskType.PLATE_MAKING,
                    foiling_plate=foiling_plate,
                    work_content=f"{order_number}制版审核",
                    production_quantity=1,
                    quantity_completed=0,
                    status=TaskStatus.PENDING,
                    auto_calculate_quantity=True,
                ))
            for embossing_plate in work_order.embossing_plates.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type=TaskType.PLATE_MAKING,
                    embossing_plate=embossing_plate,
                    work_content=f"{order_number}制版审核",
                    production_quantity=1,
                    quantity_completed=0,
                    status=TaskStatus.PENDING,
                    auto_calculate_quantity=True,
                ))

        elif process_code == ProcessCodes.CUT:
            # 开料工序：为需要开料的物料每个生成一个任务
            for material_item in work_order.materials.all():
                if material_item.need_cutting:
                    quantity = TaskGenerationService._parse_material_usage(
                        material_item.material_usage
                    )
                    tasks.append(WorkOrderTask(
                        work_order_process=work_order_process,
                        task_type=TaskType.CUTTING,
                        material=material_item.material,
                        work_content=f"{order_number}开料",
                        production_quantity=quantity,
                        quantity_completed=0,
                        status=TaskStatus.PENDING,
                        auto_calculate_quantity=True,
                    ))

        elif process_code == ProcessCodes.PRT:
            # 印刷工序：为每个图稿生成一个任务
            for artwork in work_order.artworks.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type=TaskType.PRINTING,
                    artwork=artwork,
                    work_content=f"{order_number}印刷",
                    production_quantity=production_quantity,
                    quantity_completed=0,
                    status=TaskStatus.PENDING,
                    auto_calculate_quantity=False,
                ))

        elif process_code == ProcessCodes.FOIL_G:
            # 烫金工序：为每个烫金版生成一个任务
            for foiling_plate in work_order.foiling_plates.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type=TaskType.FOILING,
                    foiling_plate=foiling_plate,
                    work_content=f"{order_number}烫金",
                    production_quantity=production_quantity,
                    quantity_completed=0,
                    status=TaskStatus.PENDING,
                    auto_calculate_quantity=False,
                ))

        elif process_code == ProcessCodes.EMB:
            # 压凸工序：为每个压凸版生成一个任务
            for embossing_plate in work_order.embossing_plates.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type=TaskType.EMBOSSING,
                    embossing_plate=embossing_plate,
                    work_content=f"{order_number}压凸",
                    production_quantity=production_quantity,
                    quantity_completed=0,
                    status=TaskStatus.PENDING,
                    auto_calculate_quantity=False,
                ))

        elif process_code == ProcessCodes.DIE:
            # 模切工序：为每个刀模生成一个任务
            for die in work_order.dies.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type=TaskType.DIE_CUTTING,
                    die=die,
                    work_content=f"{order_number}模切",
                    production_quantity=production_quantity,
                    quantity_completed=0,
                    status=TaskStatus.PENDING,
                    auto_calculate_quantity=False,
                ))

        elif process_code == ProcessCodes.PACK:
            # 包装工序：为每个产品生成一个任务
            for product_item in work_order.products.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type=TaskType.PACKAGING,
                    product=product_item.product,
                    work_content=f"{product_item.product.name}包装",
                    production_quantity=product_item.quantity,
                    quantity_completed=0,
                    status=TaskStatus.PENDING,
                    auto_calculate_quantity=False,
                ))

        else:
            # 其他工序：生成通用任务
            tasks.append(WorkOrderTask(
                work_order_process=work_order_process,
                task_type=TaskType.GENERAL,
                work_content=f"{process.name}：{order_number}",
                production_quantity=production_quantity,
                quantity_completed=0,
                status=TaskStatus.PENDING,
                auto_calculate_quantity=False,
            ))

        return tasks

    @staticmethod
    def _parse_material_usage(usage_str):
        """解析物料用量字符串，提取数字部分

        Args:
            usage_str: 物料用量字符串（如 "100张"、"50片"）

        Returns:
            int: 提取的数量
        """
        if not usage_str:
            return 0

        numbers = re.findall(r'\d+\.?\d*', usage_str)
        if numbers:
            try:
                return int(float(numbers[0]))
            except (ValueError, IndexError):
                return 0
        return 0
