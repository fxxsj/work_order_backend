"""
任务同步服务

在施工单工序修改时，使用差量更新算法同步任务。
提供预览和执行两个步骤，防止意外数据丢失。
"""
from django.db import transaction
from ..models import WorkOrder, WorkOrderProcess, WorkOrderTask
from .task_generation import TaskGenerationService


class TaskSyncService:
    """任务同步服务

    提供三路同步算法，当施工单工序被修改时：
    1. 计算集合差异（新增、删除、不变的工序）
    2. 为新增工序生成任务
    3. 删除被移除工序的任务
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
        current_process_ids = set(
            work_order.order_processes.values_list("id", flat=True)
        )
        old_set = (
            set(old_process_ids)
            if old_process_ids is not None
            else current_process_ids
        )
        new_set = (
            set(new_process_ids)
            if new_process_ids is not None
            else current_process_ids
        )

        # 计算差异
        removed = old_set - new_set  # 被移除的工序
        added = new_set - old_set    # 新增的工序

        # 查询将被删除的任务数量
        tasks_to_remove = 0
        blocked_task_ids = []
        if removed:
            removed_tasks = WorkOrderTask.objects.filter(
                work_order_process__in=list(removed),
            )
            blocked_task_ids = list(
                removed_tasks.exclude(status="pending").values_list("id", flat=True)
            )
            tasks_to_remove = removed_tasks.filter(status="pending").count()

        process_ids_to_check = (new_set & current_process_ids) | added
        missing_process_ids = []
        tasks_to_add = 0
        for process in WorkOrderProcess.objects.filter(
            id__in=list(process_ids_to_check),
            work_order=work_order,
        ):
            missing_tasks = TaskGenerationService.build_missing_task_objects(process)
            if missing_tasks:
                missing_process_ids.append(process.id)
                tasks_to_add += len(missing_tasks)

        process_ids_to_generate = sorted(set(added) | set(missing_process_ids))

        return {
            'tasks_to_remove': tasks_to_remove,
            'tasks_to_add': tasks_to_add,
            'tasks_blocked': len(blocked_task_ids),
            'removed_process_ids': list(removed),
            'added_process_ids': list(added),
            'missing_process_ids': missing_process_ids,
            'orphan_task_ids': [],
            'blocked_task_ids': blocked_task_ids,
            'process_ids_to_generate': process_ids_to_generate,
            'sync_needed': bool(removed or added or missing_process_ids),
            'affected': bool(removed or added or missing_process_ids),
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
        added_ids = preview['process_ids_to_generate']

        deleted_count = 0
        added_count = 0
        dispatched_count = 0
        blocked_task_ids = []

        # 1. 删除被移除工序的任务
        if removed_ids:
            removed_tasks = WorkOrderTask.objects.filter(
                work_order_process__in=removed_ids,
            )
            blocked_task_ids = list(
                removed_tasks.exclude(status="pending").values_list("id", flat=True)
            )
            if blocked_task_ids:
                return {
                    'deleted_count': 0,
                    'added_count': 0,
                    'dispatched_count': 0,
                    'blocked_count': len(blocked_task_ids),
                    'blocked_task_ids': blocked_task_ids,
                    'message': f'同步被阻止：{len(blocked_task_ids)} 个任务已开始或已完成，不能自动删除',
                }
            deleted_count = removed_tasks.count()
            removed_tasks.delete()

        # 2. 为新增工序生成任务
        if added_ids:
            # 获取新增的工序对象
            new_processes = WorkOrderProcess.objects.filter(
                id__in=added_ids,
                work_order=locked_work_order
            )

            all_new_tasks = []
            for process in new_processes:
                # 使用 TaskGenerationService 构建任务对象
                task_objects = TaskGenerationService.build_missing_task_objects(process)
                all_new_tasks.extend(task_objects)

            # 批量创建新任务
            if all_new_tasks:
                created_tasks = WorkOrderTask.objects.bulk_create(
                    all_new_tasks,
                    batch_size=100,
                    ignore_conflicts=False
                )
                added_count = len(created_tasks)
                dispatch_result = TaskGenerationService._dispatch_tasks(
                    created_tasks, locked_work_order
                )
                dispatched_count = dispatch_result['dispatched_count']

        message = (
            f'同步完成：已删除 {deleted_count} 个任务，'
            f'新增 {added_count} 个任务，分派 {dispatched_count} 个任务'
        )

        return {
            'deleted_count': deleted_count,
            'added_count': added_count,
            'dispatched_count': dispatched_count,
            'blocked_count': 0,
            'blocked_task_ids': blocked_task_ids,
            'message': message
        }
