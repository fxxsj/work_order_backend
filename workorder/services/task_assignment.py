"""
任务分配服务

提供任务分配的核心业务逻辑：
- TaskAssignmentService: 主管分配任务给操作员
"""
from typing import Optional, Dict, Any
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
import logging

from ..models.core import WorkOrderTask
from ..models.base import Department
from ..models.system import Notification
from ..exceptions import BusinessLogicError, PermissionDeniedError
from ..permission_utils import PermissionCache

logger = logging.getLogger(__name__)


class TaskAssignmentService:
    """任务分配服务

    处理主管手动分配任务给操作员的业务逻辑
    """

    # 默认每个操作员最多同时处理的任务数
    DEFAULT_MAX_TASKS_PER_OPERATOR = 10

    @staticmethod
    def validate_operator_task_capacity(operator, max_tasks: int = None) -> bool:
        """验证操作员任务容量

        检查操作员当前活跃任务数是否已达上限。

        Args:
            operator: 操作员用户
            max_tasks: 最大任务数限制，默认使用 DEFAULT_MAX_TASKS_PER_OPERATOR

        Returns:
            bool: 未达上限返回True

        Raises:
            BusinessLogicError: 已达上限时抛出
        """
        if max_tasks is None:
            max_tasks = TaskAssignmentService.DEFAULT_MAX_TASKS_PER_OPERATOR

        # 统计操作员当前活跃任务数（状态为 in_progress 的任务）
        active_task_count = WorkOrderTask.objects.filter(
            assigned_operator=operator,
            status='in_progress'
        ).count()

        if active_task_count >= max_tasks:
            raise BusinessLogicError(
                f"该操作员已有 {active_task_count} 个进行中任务，已达上限，"
                f"请先完成部分任务后再分配。"
            )

        return True

    @staticmethod
    def validate_supervisor_permission(user, task: WorkOrderTask) -> bool:
        """验证用户是否有权限分配该任务

        权限规则：
        1. 超级管理员可以分配所有任务
        2. 施工单创建人可以分配其施工单的任务
        3. 任务所属部门的主管可以分配该任务

        Args:
            user: 当前用户
            task: 要分配的任务

        Returns:
            bool: 有权限返回True

        Raises:
            PermissionDeniedError: 无权限时抛出
        """
        # 超级管理员
        if user.is_superuser:
            return True

        # 施工单创建人
        if task.work_order_process and task.work_order_process.work_order:
            if task.work_order_process.work_order.created_by == user:
                return True

        # 检查是否是任务所属部门的主管
        if task.assigned_department:
            if PermissionCache.is_user_in_department(user, task.assigned_department.id):
                # 检查是否有 change_workorder 权限（主管权限）
                if user.has_perm('workorder.change_workorder'):
                    return True

        raise PermissionDeniedError(
            "您没有权限分配此任务。只有任务所属部门的主管或施工单创建人可以分配。"
        )

    @staticmethod
    def validate_operator_in_department(operator, department: Department) -> bool:
        """验证操作员是否属于指定部门

        Args:
            operator: 操作员用户
            department: 部门

        Returns:
            bool: 属于部门返回True

        Raises:
            BusinessLogicError: 不属于部门时抛出
        """
        if not operator or not operator.is_active:
            raise BusinessLogicError("指定的操作员不存在或未激活")

        if not PermissionCache.is_user_in_department(operator, department.id):
            raise BusinessLogicError(
                f"操作员 {operator.username} 不属于部门 {department.name}，"
                f"无法分配该部门的任务"
            )

        return True

    @staticmethod
    def validate_task_assignment_eligibility(task: WorkOrderTask) -> bool:
        """验证任务是否可以分配

        规则：
        - 草稿状态的任务不能分配
        - 已完成的任务不能重新分配
        - 已取消的任务不能分配

        Args:
            task: 要分配的任务

        Returns:
            bool: 可以分配返回True

        Raises:
            BusinessLogicError: 不可分配时抛出
        """
        if task.status == 'draft':
            raise BusinessLogicError(
                "草稿状态的任务不能分配，请先等待施工单审核通过"
            )

        if task.status == 'completed':
            raise BusinessLogicError(
                "已完成的任务不能重新分配"
            )

        if task.status == 'cancelled':
            raise BusinessLogicError(
                "已取消的任务不能分配"
            )

        # 任务必须有分配的部门
        if not task.assigned_department:
            raise BusinessLogicError(
                "任务尚未分配到部门，无法分配操作员"
            )

        return True

    @staticmethod
    @transaction.atomic
    def assign_to_operator(task_id: int, operator_id: int, assigned_by,
                          notes: Optional[str] = None) -> Dict[str, Any]:
        """将任务分配给指定操作员

        执行步骤：
        1. 加载任务和操作员
        2. 验证分配权限
        3. 验证操作员属于任务部门
        4. 验证任务可分配性
        5. 更新任务分配信息
        6. 创建通知
        7. 记录操作日志

        Args:
            task_id: 任务ID
            operator_id: 操作员用户ID
            assigned_by: 执行分配的用户（主管）
            notes: 分配备注（可选）

        Returns:
            Dict: 包含更新后任务信息的字典

        Raises:
            PermissionDeniedError: 权限不足
            BusinessLogicError: 业务规则不满足
            WorkOrderTask.DoesNotExist: 任务不存在
        """
        from django.contrib.auth.models import User

        # 加载任务（使用 select_for_update 进行行锁）
        try:
            task = WorkOrderTask.objects.select_for_update().get(id=task_id)
        except WorkOrderTask.DoesNotExist:
            raise BusinessLogicError(f"任务ID {task_id} 不存在")

        # 加载操作员
        try:
            operator = User.objects.get(id=operator_id)
        except User.DoesNotExist:
            raise BusinessLogicError(f"操作员ID {operator_id} 不存在")

        # 验证分配权限
        TaskAssignmentService.validate_supervisor_permission(assigned_by, task)

        # 验证操作员任务容量
        TaskAssignmentService.validate_operator_task_capacity(operator)

        # 验证操作员属于任务部门
        TaskAssignmentService.validate_operator_in_department(operator, task.assigned_department)

        # 验证任务可分配性
        TaskAssignmentService.validate_task_assignment_eligibility(task)

        # 记录原操作员（用于日志）
        previous_operator = task.assigned_operator

        # 执行分配
        task.assigned_operator = operator
        task.save(update_fields=['assigned_operator', 'updated_at'])

        # 创建任务分配通知
        work_order = task.work_order_process.work_order if task.work_order_process else None
        Notification.create_notification(
            recipient=operator,
            notification_type='task_assigned',
            title=f'新任务分配：{task.work_content}',
            content=f'{assigned_by.username} 将任务 "{task.work_content}" 分配给您。'
                    f'施工单：{work_order.order_number if work_order else "N/A"}'
                    f'{f"（原操作员：{previous_operator.username}）" if previous_operator else ""}'
                    f'{f" 备注：{notes}" if notes else ""}',
            priority='normal',
            work_order=work_order,
            work_order_process=task.work_order_process,
            task=task
        )

        logger.info(
            f"任务分配：用户 {assigned_by.username} 将任务 {task_id} "
            f"分配给 {operator.username}"
        )

        return {
            'task_id': task.id,
            'assigned_operator': {
                'id': operator.id,
                'username': operator.username,
                'first_name': operator.first_name,
                'last_name': operator.last_name
            },
            'assigned_by': {
                'id': assigned_by.id,
                'username': assigned_by.username
            },
            'assigned_at': timezone.now().isoformat()
        }

    @staticmethod
    def get_department_operators(department_id: int) -> list:
        """获取部门的所有操作员

        Args:
            department_id: 部门ID

        Returns:
            list: 操作员列表，每个包含 id, username, first_name, last_name
        """
        from django.contrib.auth.models import User

        department = Department.objects.get(id=department_id)
        users = User.objects.filter(
            profile__departments=department,
            is_active=True
        ).exclude(
            is_superuser=True
        ).values('id', 'username', 'first_name', 'last_name')

        return list(users)

    @staticmethod
    def get_assignable_tasks_for_department(department_id: int, user) -> list:
        """获取用户可分配的部门任务列表

        只返回未分配操作员或可重新分配的任务

        Args:
            department_id: 部门ID
            user: 当前用户（用于权限检查）

        Returns:
            list: 可分配的任务ID列表
        """
        # 超级管理员可以分配所有任务
        if user.is_superuser:
            return list(WorkOrderTask.objects.filter(
                assigned_department_id=department_id,
                status__in=['pending', 'in_progress']
            ).values_list('id', flat=True))

        # 部门主管可以分配本部门任务
        if PermissionCache.is_user_in_department(user, department_id):
            if user.has_perm('workorder.change_workorder'):
                return list(WorkOrderTask.objects.filter(
                    assigned_department_id=department_id,
                    status__in=['pending', 'in_progress']
                ).values_list('id', flat=True))

        # 施工单创建人可以分配自己施工单的任务
        return list(WorkOrderTask.objects.filter(
            assigned_department_id=department_id,
            status__in=['pending', 'in_progress'],
            work_order_process__work_order__created_by=user
        ).values_list('id', flat=True))

    @staticmethod
    @transaction.atomic
    def claim_task(task_id: int, operator, notes: Optional[str] = None) -> Dict[str, Any]:
        """操作员认领任务

        允许操作员认领未分配的任务。使用 select_for_update 实现乐观锁，
        防止两个操作员同时认领同一任务。

        业务规则：
        - 操作员必须属于任务分配的部门
        - 任务必须已分配到部门（assigned_department 不为空）
        - 任务当前未分配给其他操作员（assigned_operator 为空）
        - 任务状态为 pending 或 in_progress
        - 草稿状态的任务不能认领

        Args:
            task_id: 任务ID
            operator: 认领任务的操作员
            notes: 认领备注（可选）

        Returns:
            Dict: 包含更新后任务信息的字典

        Raises:
            BusinessLogicError: 业务规则不满足
            WorkOrderTask.DoesNotExist: 任务不存在
        """
        from django.contrib.auth.models import User

        # 使用 select_for_update 行锁，防止并发认领
        try:
            task = WorkOrderTask.objects.select_for_update().get(id=task_id)
        except WorkOrderTask.DoesNotExist:
            raise BusinessLogicError(f"任务ID {task_id} 不存在")

        # 验证操作员属于任务部门
        if not task.assigned_department:
            raise BusinessLogicError(
                "该任务尚未分配到部门，无法认领"
            )

        if not PermissionCache.is_user_in_department(operator, task.assigned_department.id):
            raise BusinessLogicError(
                f"您不属于部门 {task.assigned_department.name}，无法认领该任务"
            )

        # 验证操作员任务容量（复用分配服务的验证方法）
        TaskAssignmentService.validate_operator_task_capacity(operator)

        # 验证任务可认领性
        if task.status == 'draft':
            raise BusinessLogicError(
                "草稿状态的任务不能认领，请先等待施工单审核通过"
            )

        if task.status == 'completed':
            raise BusinessLogicError(
                "已完成的任务不能认领"
            )

        if task.status == 'cancelled':
            raise BusinessLogicError(
                "已取消的任务不能认领"
            )

        # 检查任务是否已被其他操作员认领
        if task.assigned_operator:
            # 如果是被自己认领的，允许更新
            if task.assigned_operator.id == operator.id:
                return {
                    'task_id': task.id,
                    'assigned_operator': {
                        'id': operator.id,
                        'username': operator.username,
                        'first_name': operator.first_name,
                        'last_name': operator.last_name
                    },
                    'already_claimed': True,
                    'message': '您已经认领了该任务'
                }

            # 被其他人认领
            raise BusinessLogicError(
                f"该任务已被 {task.assigned_operator.username} 认领，无法重复认领"
            )

        # 执行认领
        task.assigned_operator = operator
        task.save(update_fields=['assigned_operator', 'updated_at'])

        # 创建任务认领通知
        work_order = task.work_order_process.work_order if task.work_order_process else None
        Notification.create_notification(
            recipient=operator,
            notification_type='task_assigned',
            title=f'任务认领成功：{task.work_content}',
            content=f'您已成功认领任务 "{task.work_content}"。'
                    f'施工单：{work_order.order_number if work_order else "N/A"}'
                    f'{f" 备注：{notes}" if notes else ""}',
            priority='normal',
            work_order=work_order,
            work_order_process=task.work_order_process,
            task=task
        )

        logger.info(
            f"任务认领：用户 {operator.username} 认领了任务 {task_id}"
        )

        return {
            'task_id': task.id,
            'assigned_operator': {
                'id': operator.id,
                'username': operator.username,
                'first_name': operator.first_name,
                'last_name': operator.last_name
            },
            'already_claimed': False,
            'message': '任务认领成功'
        }

    @staticmethod
    def get_claimable_tasks_for_user(user) -> list:
        """获取用户可认领的任务列表

        返回用户所属部门中、未分配操作员、状态为 pending 的任务

        Args:
            user: 当前用户

        Returns:
            list: 可认领的任务ID列表
        """
        if not user.is_authenticated:
            return []

        # 获取用户所属部门
        user_departments = PermissionCache.get_user_departments(user)

        if not user_departments:
            return []

        # 查询可认领的任务
        claimable_tasks = WorkOrderTask.objects.filter(
            assigned_department_id__in=user_departments,
            assigned_operator__isnull=True,
            status='pending'
        ).values_list('id', flat=True)

        return list(claimable_tasks)
