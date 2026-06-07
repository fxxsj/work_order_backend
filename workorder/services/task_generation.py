"""
任务生成服务

在施工单审核通过后自动生成正式任务，使用 bulk_create 优化性能。
任务状态为 'pending'，直接分配部门和操作员。
"""
import logging
from django.db import transaction
from ..models import WorkOrderTask, WorkOrderProcess
from ..process_codes import ProcessCodes

logger = logging.getLogger(__name__)


class TaskGenerationService:
    """任务生成服务类

    提供批量创建正式任务的方法，确保性能满足要求。
    任务生成后状态为 'pending'，并自动分派到部门和操作员。
    """

    @staticmethod
    def generate_tasks_and_dispatch(work_order):
        """为施工单审核通过后生成正式任务并自动分派

        Args:
            work_order: WorkOrder 实例

        Returns:
            dict: {
                'created_count': 创建的任务数量,
                'dispatched_count': 分派的任务数量,
                'tasks': 创建的任务列表
            }
        """
        all_tasks = []
        existing_count = WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order
        ).exclude(status="draft").count()

        # 遍历施工单的所有工序
        for work_order_process in work_order.order_processes.all():
            # 为每个工序构建任务对象
            tasks = TaskGenerationService.build_missing_task_objects(work_order_process)
            all_tasks.extend(tasks)

        if not all_tasks:
            logger.info(f"施工单 {work_order.order_number} 没有需要生成的任务")
            return {
                'created_count': 0,
                'existing_count': existing_count,
                'dispatched_count': 0,
                'skipped_count': existing_count,
                'tasks': [],
            }

        # 批量创建所有任务
        created_tasks = WorkOrderTask.objects.bulk_create(
            all_tasks,
            batch_size=100,
        )

        # 批量分派任务
        dispatch_result = TaskGenerationService._dispatch_tasks(created_tasks, work_order)

        logger.info(
            f"施工单 {work_order.order_number} 生成了 {len(created_tasks)} 个任务，"
            f"分派了 {dispatch_result['dispatched_count']} 个，"
            f"未分派 {dispatch_result['undispatched_count']} 个"
        )

        return {
            'created_count': len(created_tasks),
            'existing_count': existing_count,
            'dispatched_count': dispatch_result['dispatched_count'],
            'undispatched_count': dispatch_result['undispatched_count'],
            'undispatched_reasons': dispatch_result['undispatched_reasons'],
            'skipped_count': existing_count,
            'tasks': list(created_tasks)
        }

    @staticmethod
    def build_missing_task_objects(work_order_process):
        """构建当前工序缺失的任务对象，避免重复生成。"""
        task_objects = TaskGenerationService.build_task_objects(work_order_process)
        return [
            task for task in task_objects
            if not TaskGenerationService._task_exists(task)
        ]

    @staticmethod
    @transaction.atomic
    def generate_tasks_for_process(work_order_process):
        """兼容单工序补生成入口，复用正式任务生成规则。"""
        task_objects = TaskGenerationService.build_missing_task_objects(
            work_order_process
        )
        if not task_objects:
            return []

        created_tasks = WorkOrderTask.objects.bulk_create(task_objects, batch_size=100)
        TaskGenerationService._dispatch_tasks(
            created_tasks,
            work_order_process.work_order,
        )
        return list(created_tasks)

    @staticmethod
    def _task_exists(task):
        """按生成规则的任务身份判断任务是否已存在。"""
        filters = {
            "work_order_process": task.work_order_process,
            "task_type": task.task_type,
            "artwork": task.artwork,
            "die": task.die,
            "product": task.product,
            "material": task.material,
            "foiling_plate": task.foiling_plate,
            "embossing_plate": task.embossing_plate,
            "parent_task__isnull": True,
        }
        return WorkOrderTask.objects.filter(**filters).exclude(status="draft").exists()

    @staticmethod
    def build_task_objects(work_order_process):
        """为工序构建正式任务对象（不保存到数据库）

        返回未保存的 WorkOrderTask 实例列表，用于批量创建。
        任务的特点：
        - status='pending' 直接为正式状态
        - 不分配操作员（由 _dispatch_tasks 后续分派）
        - 不分配部门（由 _dispatch_tasks 后续分派）

        Args:
            work_order_process: WorkOrderProcess 实例

        Returns:
            list: 未保存的 WorkOrderTask 对象列表
        """
        process = work_order_process.process
        work_order = work_order_process.work_order
        process_code = process.code
        order_number = work_order.order_number
        production_quantity = work_order.production_quantity or 0

        tasks = []

        # 根据工序编码生成不同类型的任务
        if process_code == ProcessCodes.CTP:
            # 制版工序：为图稿、刀模、烫金版、压凸版每个生成一个任务
            for artwork in work_order.artworks.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type='plate_making',
                    artwork=artwork,
                    work_content=f'{order_number}制版审核',
                    production_quantity=1,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=True
                ))
            for die in work_order.dies.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type='plate_making',
                    die=die,
                    work_content=f'{order_number}制版审核',
                    production_quantity=1,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=True
                ))
            for foiling_plate in work_order.foiling_plates.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type='plate_making',
                    foiling_plate=foiling_plate,
                    work_content=f'{order_number}制版审核',
                    production_quantity=1,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=True
                ))
            for embossing_plate in work_order.embossing_plates.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type='plate_making',
                    embossing_plate=embossing_plate,
                    work_content=f'{order_number}制版审核',
                    production_quantity=1,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=True
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
                        task_type='cutting',
                        material=material_item.material,
                        work_content=f'{order_number}开料',
                        production_quantity=quantity,
                        quantity_completed=0,
                        status='pending',
                        auto_calculate_quantity=True
                    ))

        elif process_code == ProcessCodes.PRT:
            # 印刷工序：为每个图稿生成一个任务
            for artwork in work_order.artworks.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type='printing',
                    artwork=artwork,
                    work_content=f'{order_number}印刷',
                    production_quantity=production_quantity,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=False
                ))

        elif process_code == ProcessCodes.FOIL_G:
            # 烫金工序：为每个烫金版生成一个任务
            for foiling_plate in work_order.foiling_plates.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type='foiling',
                    foiling_plate=foiling_plate,
                    work_content=f'{order_number}烫金',
                    production_quantity=production_quantity,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=False
                ))

        elif process_code == ProcessCodes.EMB:
            # 压凸工序：为每个压凸版生成一个任务
            for embossing_plate in work_order.embossing_plates.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type='embossing',
                    embossing_plate=embossing_plate,
                    work_content=f'{order_number}压凸',
                    production_quantity=production_quantity,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=False
                ))

        elif process_code == ProcessCodes.DIE:
            # 模切工序：为每个刀模生成一个任务
            for die in work_order.dies.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type='die_cutting',
                    die=die,
                    work_content=f'{order_number}模切',
                    production_quantity=production_quantity,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=False
                ))

        elif process_code == ProcessCodes.PACK:
            # 包装工序：为每个产品生成一个任务
            for product_item in work_order.products.all():
                tasks.append(WorkOrderTask(
                    work_order_process=work_order_process,
                    task_type='packaging',
                    product=product_item.product,
                    work_content=f'{product_item.product.name}包装',
                    production_quantity=product_item.quantity,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=False
                ))

        else:
            # 其他工序：生成通用任务
            tasks.append(WorkOrderTask(
                work_order_process=work_order_process,
                task_type='general',
                work_content=f'{process.name}：{order_number}',
                production_quantity=production_quantity,
                quantity_completed=0,
                status='pending',
                auto_calculate_quantity=False
            ))

        return tasks

    @staticmethod
    def _dispatch_tasks(tasks, work_order):
        """批量分派任务到部门和操作员

        Args:
            tasks: WorkOrderTask 对象列表
            work_order: 施工单对象

        Returns:
            dict: {
                'dispatched_count': 已分派到部门的任务数,
                'undispatched_count': 未分派到部门的任务数,
                'undispatched_reasons': 未分派原因列表,
            }
        """
        dispatched_count = 0
        undispatched_count = 0
        undispatched_reasons = []

        for task in tasks:
            work_order_process = task.work_order_process
            if work_order_process:
                # 使用工序的分派逻辑
                work_order_process._auto_assign_task(task)
                if task.assigned_department_id:
                    dispatched_count += 1
                else:
                    undispatched_count += 1
                    reason = (
                        f"工序 {work_order_process.process.name} "
                        f"未配置负责部门或分派规则"
                    )
                    undispatched_reasons.append(reason)

        return {
            'dispatched_count': dispatched_count,
            'undispatched_count': undispatched_count,
            'undispatched_reasons': undispatched_reasons,
        }

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

        import re
        numbers = re.findall(r'\d+\.?\d*', usage_str)
        if numbers:
            try:
                return int(float(numbers[0]))
            except (ValueError, IndexError):
                return 0
        return 0
