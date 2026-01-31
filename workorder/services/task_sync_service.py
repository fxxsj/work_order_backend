"""
任务同步服务

在施工单工序修改时，使用差量更新算法同步草稿任务。
提供预览和执行两个步骤，防止意外数据丢失。
"""
from django.db import transaction
from ..models import WorkOrder, WorkOrderProcess, WorkOrderTask
from .task_generation import DraftTaskGenerationService


class TaskSyncService:
    """任务同步服务类

    提供三路同步算法，当施工单工序被修改时：
    1. 计算集合差异（新增、删除、不变的工序）
    2. 为新增工序生成草稿任务
    3. 删除被移除工序的草稿任务（仅限草稿状态）
    """

    @staticmethod
    def preview_sync(work_order, old_process_ids, new_process_ids):
        """预览同步变更（不修改数据库）

        计算如果执行同步会发生什么变化，返回预览信息供用户确认。

        Args:
            work_order: WorkOrder 实例
            old_process_ids: 原工序ID列表
            new_process_ids: 新工序ID列表

        Returns:
            dict: 预览信息，包含：
                - tasks_to_remove: 将要删除的任务数量
                - tasks_to_add: 预计新增的任务数量（估算值）
                - removed_process_ids: 被移除的工序ID列表
                - added_process_ids: 新增的工序ID列表
                - affected: 是否有任何变化
        """
        # 使用集合进行差量计算（O(1)复杂度）
        old_set = set(old_process_ids)
        new_set = set(new_process_ids)

        # 计算差异
        removed = old_set - new_set  # 被移除的工序
        added = new_set - old_set    # 新增的工序

        # 查询将被删除的草稿任务数量
        tasks_to_remove = 0
        if removed:
            tasks_to_remove = WorkOrderTask.objects.filter(
                work_order_process__in=list(removed),
                status='draft'
            ).count()

        # 估算新增任务数量（基于工序类型）
        # 这是一个粗略估计，实际数量取决于工序类型和关联对象
        tasks_to_add = len(added) * 2  # 保守估计每个工序平均生成2个任务

        return {
            'tasks_to_remove': tasks_to_remove,
            'tasks_to_add': tasks_to_add,
            'removed_process_ids': list(removed),
            'added_process_ids': list(added),
            'affected': len(removed) > 0 or len(added) > 0
        }

    @staticmethod
    @transaction.atomic
    def execute_sync(work_order, old_process_ids, new_process_ids):
        """执行任务同步（原子操作）

        先调用 preview_sync 计算变更，然后执行实际的同步操作。
        使用 select_for_update() 锁定施工单，防止并发修改。
        所有操作在事务中执行，确保失败时回滚。

        Args:
            work_order: WorkOrder 实例
            old_process_ids: 原工序ID列表
            new_process_ids: 新工序ID列表

        Returns:
            dict: 执行结果，包含：
                - deleted_count: 删除的任务数量
                - added_count: 新增的任务数量
                - message: 操作结果消息
        """
        # 锁定施工单，防止并发修改
        locked_work_order = WorkOrder.objects.select_for_update().get(id=work_order.id)

        # 先计算预览，确认变更内容
        preview = TaskSyncService.preview_sync(
            locked_work_order, old_process_ids, new_process_ids
        )

        removed_ids = preview['removed_process_ids']
        added_ids = preview['added_process_ids']

        deleted_count = 0
        added_count = 0

        # 1. 删除被移除工序的草稿任务
        if removed_ids:
            deleted_count, _ = WorkOrderTask.objects.filter(
                work_order_process__in=removed_ids,
                status='draft'  # 仅删除草稿任务，不影响正式任务
            ).delete()

        # 2. 为新增工序生成草稿任务
        if added_ids:
            # 获取新增的工序对象
            new_processes = WorkOrderProcess.objects.filter(
                id__in=added_ids,
                work_order=locked_work_order
            )

            all_new_tasks = []
            for process in new_processes:
                # 使用 DraftTaskGenerationService 构建任务对象
                task_objects = DraftTaskGenerationService.build_task_objects(process)
                all_new_tasks.extend(task_objects)

            # 批量创建新任务
            if all_new_tasks:
                created_tasks = WorkOrderTask.objects.bulk_create(
                    all_new_tasks,
                    batch_size=100,
                    ignore_conflicts=False
                )
                added_count = len(created_tasks)

        message = f'同步完成：已删除 {deleted_count} 个草稿任务，新增 {added_count} 个草稿任务'

        return {
            'deleted_count': deleted_count,
            'added_count': added_count,
            'message': message
        }
