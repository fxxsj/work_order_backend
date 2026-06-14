"""任务操作服务

将 TaskActionsMixin 中的业务逻辑下沉到服务层，视图只负责序列化和响应。
"""

import logging
from typing import Optional

from django.contrib.auth.models import User
from rest_framework import status

from ..models.base import Department
from ..models.core import TaskLog, WorkOrderTask
from ..models.system import Notification
from ..policies.task_policy import (
    ensure_assets_confirmed,
    ensure_material_cut_ready,
)
from ..services.realtime_notification import notification_service
from ..services.task_assignment import TaskAssignmentService
from ..services.service_errors import ServiceError

logger = logging.getLogger(__name__)


class TaskActionService:
    """任务操作服务"""

    @staticmethod
    def update_quantity(
        *,
        task: WorkOrderTask,
        quantity_increment,
        quantity_defective: int = 0,
        notes: str = "",
        work_hours=None,
        machine_name: str = "",
        operator_count=None,
        user: User,
    ) -> WorkOrderTask:
        """更新任务完成数量并自动判断状态。"""
        work_order_process = task.work_order_process
        work_order = work_order_process.work_order
        process_code = work_order_process.process.code

        if quantity_increment is None:
            raise ServiceError(
                "请提供本次完成数量", code=status.HTTP_400_BAD_REQUEST
            )

        quantity_before = task.quantity_completed
        new_quantity_completed = quantity_before + quantity_increment

        ensure_assets_confirmed(task, "更新")
        ensure_material_cut_ready(task, process_code, work_order, "更新")

        if new_quantity_completed < 0:
            raise ServiceError(
                "更新后完成数量不能小于0", code=status.HTTP_400_BAD_REQUEST
            )
        if (
            task.production_quantity
            and new_quantity_completed > task.production_quantity
        ):
            raise ServiceError(
                f"更新后完成数量（{new_quantity_completed}）不能超过生产数量（{task.production_quantity}）",
                code=status.HTTP_400_BAD_REQUEST,
            )

        status_before = task.status

        task.quantity_completed = new_quantity_completed
        if quantity_defective is not None:
            task.quantity_defective = (task.quantity_defective or 0) + quantity_defective
        if notes:
            task.production_requirements = notes
        if work_hours is not None:
            try:
                task.work_hours = float(work_hours)
            except (TypeError, ValueError):
                pass
        if machine_name:
            task.machine_name = machine_name
        if operator_count is not None:
            try:
                task.operator_count = int(operator_count)
            except (TypeError, ValueError):
                pass

        if (
            task.production_quantity
            and new_quantity_completed >= task.production_quantity
        ):
            task.status = "completed"
        else:
            if task.status == "pending":
                task.status = "in_progress"
            elif (
                task.status == "completed"
                and new_quantity_completed < task.production_quantity
            ):
                task.status = "in_progress"

        task.save()

        # 包装任务库存调整
        stock_increment = new_quantity_completed - (task.stock_accounted_quantity or 0)
        if stock_increment != 0 and task.product:
            try:
                if stock_increment > 0:
                    task.product.add_stock(
                        quantity=stock_increment,
                        user=None,
                        reason=f"施工单{work_order.order_number}包装任务数量编辑，入库{stock_increment}{task.product.unit}",
                    )
                else:
                    try:
                        task.product.reduce_stock(
                            quantity=abs(stock_increment),
                            user=None,
                            reason=f"施工单{work_order.order_number}包装任务数量编辑，出库{abs(stock_increment)}{task.product.unit}",
                        )
                    except ValueError as e:
                        logger.warning(f"库存不足警告：{e}")
            except Exception as e:
                logger.error(f"调整产品库存失败：{e}")

            task.stock_accounted_quantity = new_quantity_completed
            task.save(update_fields=["stock_accounted_quantity"])

        defective_increment = quantity_defective if quantity_defective else 0
        TaskLog.objects.create(
            task=task,
            log_type="update_quantity",
            content=f"更新完成数量：{quantity_before} → {new_quantity_completed}，本次完成：{quantity_increment}，不良品：{defective_increment}，状态：{status_before} → {task.status}"
            + (f"，备注：{notes}" if notes else ""),
            quantity_before=quantity_before,
            quantity_after=new_quantity_completed,
            quantity_increment=quantity_increment,
            quantity_defective_increment=defective_increment,
            status_before=status_before,
            status_after=task.status,
            operator=user,
        )

        if task.is_subtask() and task.parent_task:
            task.parent_task.update_from_subtasks()

        task.work_order_process.check_and_update_status()
        return task

    @staticmethod
    def complete_task(
        *,
        task: WorkOrderTask,
        completion_reason: str = "",
        quantity_defective: int = 0,
        notes: str = "",
        user: User,
    ) -> WorkOrderTask:
        """强制完成任务。"""
        work_order_process = task.work_order_process
        work_order = work_order_process.work_order
        process_code = work_order_process.process.code

        ensure_assets_confirmed(task, "完成")
        ensure_material_cut_ready(task, process_code, work_order, "完成")

        status_before = task.status
        quantity_before = task.quantity_completed

        task.status = "completed"
        if notes:
            task.production_requirements = notes

        if task.task_type == "plate_making":
            task.quantity_completed = 1
        else:
            task.quantity_completed = task.production_quantity

        if quantity_defective is not None:
            task.quantity_defective = quantity_defective

        task.save()

        quantity_increment = task.quantity_completed - quantity_before
        defective_increment = quantity_defective if quantity_defective else 0

        log_content = f"强制完成任务，完成数量：{quantity_before} → {task.quantity_completed}，不良品：{defective_increment}，状态：{status_before} → completed"
        if quantity_increment != 0:
            log_content += f"，本次完成：{quantity_increment}"
        if completion_reason:
            log_content += f"，完成理由：{completion_reason}"
        if notes:
            log_content += f"，备注：{notes}"

        TaskLog.objects.create(
            task=task,
            log_type="complete",
            content=log_content,
            quantity_before=quantity_before,
            quantity_after=task.quantity_completed,
            quantity_increment=quantity_increment,
            quantity_defective_increment=defective_increment,
            status_before=status_before,
            status_after="completed",
            completion_reason=completion_reason,
            operator=user,
        )

        notification_service.notify_task_completed(task=task, completed_by=user)

        if task.is_subtask() and task.parent_task:
            task.parent_task.update_from_subtasks()

        task.work_order_process.check_and_update_status()
        return task

    @staticmethod
    def split_task(*, task: WorkOrderTask, splits: list, user: User) -> dict:
        """拆分任务为多个子任务。

        Returns:
            dict: {"parent_task": task, "created_subtasks": [...], "total_split_quantity": int}

        Raises:
            ServiceError: 业务规则不满足时抛出
        """
        if task.subtasks.exists():
            raise ServiceError(
                "该任务已经拆分，无法再次拆分", code=status.HTTP_400_BAD_REQUEST
            )
        if task.status == "completed":
            raise ServiceError(
                "已完成的任务无法拆分", code=status.HTTP_400_BAD_REQUEST
            )

        if not splits or len(splits) < 2:
            raise ServiceError(
                "至少需要拆分为2个子任务", code=status.HTTP_400_BAD_REQUEST
            )

        total_split_quantity = sum(s.get("production_quantity", 0) for s in splits)
        if total_split_quantity > task.production_quantity:
            raise ServiceError(
                f"子任务数量总和（{total_split_quantity}）不能超过父任务数量（{task.production_quantity}）",
                code=status.HTTP_400_BAD_REQUEST,
            )

        created_subtasks = []
        for idx, split_data in enumerate(splits):
            production_quantity = split_data.get("production_quantity", 0)
            if production_quantity <= 0:
                raise ServiceError(
                    f"第{idx+1}个子任务的生产数量必须大于0",
                    code=status.HTTP_400_BAD_REQUEST,
                )

            work_content = split_data.get(
                "work_content", f"{task.work_content}（子任务{idx+1}）"
            )

            subtask = WorkOrderTask.objects.create(
                work_order_process=task.work_order_process,
                task_type=task.task_type,
                work_content=work_content,
                production_quantity=production_quantity,
                quantity_completed=0,
                quantity_defective=0,
                parent_task=task,
                assigned_department_id=split_data.get("assigned_department"),
                assigned_operator_id=split_data.get("assigned_operator"),
                artwork=task.artwork,
                die=task.die,
                product=task.product,
                material=task.material,
                foiling_plate=task.foiling_plate,
                embossing_plate=task.embossing_plate,
                production_requirements=task.production_requirements,
                status="pending",
                auto_calculate_quantity=task.auto_calculate_quantity,
            )
            created_subtasks.append(subtask)

        if task.status == "pending":
            task.status = "in_progress"
            task.save()

        TaskLog.objects.create(
            task=task,
            log_type="status_change",
            content=f"任务已拆分为{len(created_subtasks)}个子任务，子任务数量总和：{total_split_quantity}",
            operator=user,
        )

        return {
            "parent_task": task,
            "created_subtasks": created_subtasks,
            "total_split_quantity": total_split_quantity,
        }
    @staticmethod
    def assign_task(
        *,
        task: WorkOrderTask,
        assigned_department: Optional[int] = None,
        assigned_operator: Optional[int] = None,
        notes: str = "",
        reason: str = "",
        user: User,
    ) -> dict:
        """分派任务给部门或操作员。

        Returns:
            dict: 包含 operator_assignment_result（操作员分派结果，可能为 None）
        """
        result = None

        if assigned_department is not None:
            TaskAssignmentService.validate_supervisor_permission(user, task)
            old_department = task.assigned_department
            old_operator = task.assigned_operator

            department = None
            if assigned_department:
                try:
                    department = Department.objects.get(
                        id=assigned_department, is_active=True
                    )
                except Department.DoesNotExist as exc:
                    raise ServiceError(
                        "部门不存在或已停用", code=status.HTTP_404_NOT_FOUND
                    ) from exc

                if not department.processes.filter(
                    id=task.work_order_process.process.id
                ).exists():
                    raise ServiceError(
                        f"部门 {department.name} 不负责工序 {task.work_order_process.process.name}，无法分配",
                        code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )

            if task.assigned_department_id != assigned_department:
                task.assigned_department = department
                if old_operator and department:
                    try:
                        TaskAssignmentService.validate_operator_in_department(
                            old_operator, department
                        )
                    except ServiceError:
                        task.assigned_operator = None
                elif not department:
                    task.assigned_operator = None

                task.save(
                    update_fields=[
                        "assigned_department",
                        "assigned_operator",
                        "updated_at",
                    ]
                )

                old_department_name = old_department.name if old_department else "未分配"
                new_department_name = department.name if department else "未分配"
                log_content = (
                    f"调整任务分派部门：{old_department_name} → {new_department_name}"
                )
                if old_operator and task.assigned_operator_id != old_operator.id:
                    old_operator_name = (
                        f"{old_operator.first_name}{old_operator.last_name}"
                        or old_operator.username
                    )
                    log_content += f"，清空原操作员：{old_operator_name}"
                if reason:
                    log_content += f"，原因：{reason}"
                if notes:
                    log_content += f"，备注：{notes}"

                TaskLog.objects.create(
                    task=task,
                    log_type="status_change",
                    content=log_content,
                    operator=user,
                )

        if assigned_operator:
            result = TaskAssignmentService.assign_to_operator(
                task_id=task.id,
                operator_id=assigned_operator,
                assigned_by=user,
                notes=notes,
            )

        return {"operator_assignment_result": result}

    @staticmethod
    def cancel_task(
        *,
        task: WorkOrderTask,
        cancellation_reason: str,
        notes: str = "",
        user: User,
    ) -> WorkOrderTask:
        """取消任务。

        Raises:
            ServiceError: 权限不足或业务规则不满足时抛出
        """
        if task.status == "cancelled":
            raise ServiceError(
                "任务已经取消，无法重复取消", code=status.HTTP_400_BAD_REQUEST
            )
        if task.status == "completed":
            raise ServiceError(
                "已完成的任务无法取消", code=status.HTTP_400_BAD_REQUEST
            )

        can_cancel = (
            user.has_perm("workorder.change_workorder")
            or task.assigned_operator == user
            or task.work_order_process.work_order.created_by == user
        )
        if not can_cancel:
            raise ServiceError(
                "您没有权限取消此任务", code=status.HTTP_403_FORBIDDEN
            )

        work_order_process = task.work_order_process
        if work_order_process.tasks.count() == 1 and work_order_process.status != "pending":
            raise ServiceError(
                "该任务是工序的唯一任务，取消后工序无法完成。请先处理工序状态",
                code=status.HTTP_400_BAD_REQUEST,
            )

        status_before = task.status
        task.status = "cancelled"
        task.save()

        log_content = f"取消任务，原因：{cancellation_reason}"
        if notes:
            log_content += f"，备注：{notes}"

        TaskLog.objects.create(
            task=task,
            log_type="status_change",
            content=log_content,
            status_before=status_before,
            status_after="cancelled",
            operator=user,
        )

        if task.assigned_operator:
            Notification.create_notification(
                recipient=task.assigned_operator,
                notification_type="task_cancelled",
                title="任务已取消",
                content=f'任务 "{task.work_content}" 已被取消',
                priority="normal",
                work_order=work_order_process.work_order,
                work_order_process=work_order_process,
                task=task,
                template_key="task_cancelled",
                template_variables={
                    "task_name": task.work_content,
                    "workorder_number": work_order_process.work_order.order_number,
                    "cancellation_reason": cancellation_reason,
                },
            )

        return task
