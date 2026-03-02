"""
施工单工序相关服务

将 WorkOrderProcessViewSet 中的业务逻辑下沉到服务层，保持 views 层职责单一。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone
from rest_framework import status

from ..models.core import ProcessLog, TaskLog, WorkOrderProcess
from ..models.base import Department
from .service_errors import ServiceError


class WorkOrderProcessService:
    @staticmethod
    def start_process(
        *,
        process: WorkOrderProcess,
        user,
        operator_id: Optional[int] = None,
        department_id: Optional[int] = None,
    ) -> WorkOrderProcess:
        if not process.can_start():
            raise ServiceError(
                "该工序不能开始，请先完成前置工序",
                code=status.HTTP_400_BAD_REQUEST,
            )

        if process.status != "pending":
            raise ServiceError(
                "该工序已经开始或完成，不能重新开始",
                code=status.HTTP_400_BAD_REQUEST,
            )

        process.generate_tasks()

        process.status = "in_progress"
        process.actual_start_time = timezone.now()
        if operator_id:
            process.operator_id = operator_id
        if department_id:
            process.department_id = department_id
        process.save()

        ProcessLog.objects.create(
            work_order_process=process,
            log_type="start",
            content="开始工序",
            operator=user,
        )

        process.generate_tasks()
        return process

    @staticmethod
    def complete_process(
        *,
        process: WorkOrderProcess,
        user,
        quantity_completed: int = 0,
        quantity_defective: int = 0,
        force_complete: bool = False,
        force_reason: str = "",
    ) -> WorkOrderProcess:
        if process.status != "in_progress":
            raise ServiceError(
                "只有进行中的工序才能完成",
                code=status.HTTP_400_BAD_REQUEST,
            )

        tasks = process.tasks.all()
        incomplete_tasks = tasks.exclude(status="completed")

        if incomplete_tasks.exists():
            if process.check_and_update_status():
                if quantity_defective > 0:
                    process.quantity_defective = quantity_defective
                if quantity_completed > 0:
                    process.quantity_completed = quantity_completed
                process.save()

                ProcessLog.objects.create(
                    work_order_process=process,
                    log_type="complete",
                    content=f"自动完成工序（所有任务已完成），完成数量：{process.quantity_completed}，不良品数量：{process.quantity_defective}",
                    operator=user,
                )
                return process

            if not force_complete:
                incomplete_count = incomplete_tasks.count()
                raise ServiceError(
                    f"该工序还有 {incomplete_count} 个任务未完成，无法完成工序",
                    code=status.HTTP_400_BAD_REQUEST,
                    data={
                        "incomplete_tasks": incomplete_count,
                        "requires_force": True,
                        "hint": "请先完成所有任务，或提供强制完成原因进行强制完成",
                    },
                )

            if not force_reason:
                raise ServiceError(
                    "强制完成工序需要提供完成原因",
                    code=status.HTTP_400_BAD_REQUEST,
                )

            for task in incomplete_tasks:
                task.status = "completed"
                if task.production_quantity and not task.quantity_completed:
                    task.quantity_completed = task.production_quantity
                task.save()

                TaskLog.objects.create(
                    task=task,
                    log_type="status_change",
                    content=f"强制完成（因工序强制完成），原因：{force_reason}",
                    operator=user,
                )

        process.quantity_completed = quantity_completed
        process.quantity_defective = quantity_defective
        process.status = "completed"
        process.actual_end_time = timezone.now()
        process.save()

        log_content = f"完成工序，完成数量：{quantity_completed}，不良品数量：{quantity_defective}"
        if force_complete:
            log_content += f"（强制完成，原因：{force_reason}）"

        ProcessLog.objects.create(
            work_order_process=process,
            log_type="complete",
            content=log_content,
            operator=user,
        )

        work_order = process.work_order
        all_processes_completed = (
            work_order.order_processes.exclude(status="completed").count() == 0
        )
        if all_processes_completed and work_order.status != "completed":
            work_order.status = "completed"
            work_order.save()

        return process

    @staticmethod
    def batch_start(
        *,
        process_ids: List[int],
        user,
        operator_id: Optional[int] = None,
        department_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not process_ids:
            raise ServiceError(
                "请提供工序ID列表",
                code=status.HTTP_400_BAD_REQUEST,
            )

        processes = WorkOrderProcess.objects.filter(id__in=process_ids)
        if processes.count() != len(process_ids):
            raise ServiceError(
                "部分工序不存在",
                code=status.HTTP_400_BAD_REQUEST,
            )

        started_processes: List[int] = []
        failed_processes: List[Dict[str, Any]] = []

        for process in processes:
            try:
                if not process.can_start():
                    failed_processes.append(
                        {"process_id": process.id, "error": "该工序不能开始，请先完成前置工序"}
                    )
                    continue

                if process.status != "pending":
                    failed_processes.append(
                        {"process_id": process.id, "error": "该工序已经开始或完成，不能重新开始"}
                    )
                    continue

                process.generate_tasks()

                process.status = "in_progress"
                process.actual_start_time = timezone.now()
                if operator_id:
                    process.operator_id = operator_id
                if department_id:
                    process.department_id = department_id
                process.save()

                ProcessLog.objects.create(
                    work_order_process=process,
                    log_type="start",
                    content="批量开始工序",
                    operator=user,
                )

                started_processes.append(process.id)
            except Exception as exc:
                failed_processes.append({"process_id": process.id, "error": str(exc)})

        return {
            "message": f"成功开始 {len(started_processes)} 个工序，失败 {len(failed_processes)} 个",
            "started_count": len(started_processes),
            "failed_count": len(failed_processes),
            "started_process_ids": started_processes,
            "failed_processes": failed_processes,
        }

    @staticmethod
    def reassign_tasks(
        *,
        work_order_process: WorkOrderProcess,
        user,
        department_id,
        operator_id,
        reason: str,
        notes: str = "",
        update_process_department: bool = False,
    ) -> Dict[str, Any]:
        if not reason:
            raise ServiceError(
                "调整原因不能为空，请说明为什么需要调整分派",
                code=status.HTTP_400_BAD_REQUEST,
            )

        tasks = work_order_process.tasks.all()
        if not tasks.exists():
            raise ServiceError(
                "该工序还没有生成任务",
                code=status.HTTP_400_BAD_REQUEST,
            )

        new_department = None
        if department_id:
            try:
                new_department = Department.objects.get(id=department_id)
            except Department.DoesNotExist as exc:
                raise ServiceError(
                    "部门不存在",
                    code=status.HTTP_404_NOT_FOUND,
                ) from exc

        new_operator = None
        if operator_id:
            try:
                from django.contrib.auth.models import User

                new_operator = User.objects.get(id=operator_id)
            except User.DoesNotExist as exc:
                raise ServiceError(
                    "操作员不存在",
                    code=status.HTTP_404_NOT_FOUND,
                ) from exc

        updated_count = 0
        for task in tasks:
            changed = False
            old_dept = task.assigned_department
            old_op = task.assigned_operator

            if department_id is not None:
                if department_id:
                    task.assigned_department = new_department
                    changed = changed or (old_dept != new_department)
                else:
                    task.assigned_department = None
                    changed = changed or (old_dept is not None)

            if operator_id is not None:
                if operator_id:
                    task.assigned_operator = new_operator
                    changed = changed or (old_op != new_operator)
                else:
                    task.assigned_operator = None
                    changed = changed or (old_op is not None)

            if changed:
                task.save()
                updated_count += 1

                changes: List[str] = []
                if department_id is not None:
                    old_dept_name = old_dept.name if old_dept else "未分配"
                    new_dept_name = new_department.name if new_department else "未分配"
                    changes.append(f"部门：{old_dept_name} → {new_dept_name}")

                if operator_id is not None:
                    old_op_name = (
                        f"{old_op.first_name}{old_op.last_name}" if old_op else "未分配"
                    )
                    new_op_name = (
                        f"{new_operator.first_name}{new_operator.last_name}"
                        if new_operator
                        else "未分配"
                    )
                    changes.append(f"操作员：{old_op_name} → {new_op_name}")

                log_content = f'批量调整任务分派：{", ".join(changes)}，原因：{reason}'
                if notes:
                    log_content += f"，备注：{notes}"

                TaskLog.objects.create(
                    task=task,
                    log_type="status_change",
                    content=log_content,
                    operator=user,
                )

        if update_process_department and department_id:
            work_order_process.department = new_department
            work_order_process.save()

        return {
            "updated_tasks_count": updated_count,
            "total_tasks_count": tasks.count(),
        }
