"""
多级审核相关的服务层动作
"""

from __future__ import annotations

from django.utils import timezone

from workorder.services.service_errors import ServiceError

from ..models.core import WorkOrder, WorkOrderTask
from ..models.multi_level_approval import (
    ApprovalEscalation,
    ApprovalStep,
    ApprovalWorkflow,
    MultiLevelApprovalService,
    UrgentOrderService,
)
from ..services.smart_assignment import SmartAssignmentService


def activate_workflow(workflow: ApprovalWorkflow) -> ApprovalWorkflow:
    workflow.is_active = True
    workflow.save(update_fields=["is_active"])
    return workflow


def deactivate_workflow(workflow: ApprovalWorkflow) -> ApprovalWorkflow:
    workflow.is_active = False
    workflow.save(update_fields=["is_active"])
    return workflow


def create_default_workflows(user):
    workflow_types = ["simple", "standard", "complex", "urgent"]
    created = []
    for workflow_type in workflow_types:
        workflow = MultiLevelApprovalService.create_default_workflow(
            workflow_type, user
        )
        created.append(workflow)
    return created


def duplicate_workflow(*, source_id: str, new_name: str, user) -> ApprovalWorkflow:
    if not source_id or not new_name:
        raise ServiceError(message="请提供源工作流ID和新名称", code=400)

    try:
        source_workflow = ApprovalWorkflow.objects.get(id=source_id)
    except ApprovalWorkflow.DoesNotExist as exc:
        raise ServiceError(message="源工作流不存在", code=404) from exc

    return ApprovalWorkflow.objects.create(
        name=new_name,
        workflow_type=source_workflow.workflow_type,
        description=f"复制自 {source_workflow.name}",
        steps=source_workflow.steps,
        is_active=False,
        created_by=user,
    )


def start_step(step: ApprovalStep) -> ApprovalStep:
    if step.status != "pending":
        raise ServiceError(message="只能开始待执行的步骤", code=400)

    step.status = "in_progress"
    step.started_at = timezone.now()
    step.save(update_fields=["status", "started_at"])
    return step


def complete_step(step: ApprovalStep, decision: str, comments: str, user) -> None:
    success = MultiLevelApprovalService.complete_approval_step(
        step, decision, comments, user
    )
    if not success:
        raise ServiceError(message="步骤完成失败", code=400)


def escalate_step(
    *,
    step: ApprovalStep,
    escalation_reason: str,
    to_step_id: str | None,
    user,
) -> ApprovalEscalation:
    escalation = ApprovalEscalation.objects.create(
        work_order=step.work_order,
        from_step=step,
        to_step_id=to_step_id,
        escalation_reason=escalation_reason,
        escalated_by=user,
        status="pending",
    )

    step.status = "completed"
    step.decision = "escalate"
    step.completed_at = timezone.now()
    step.save(update_fields=["status", "decision", "completed_at"])
    return escalation


def submit_for_approval(*, order_id: str, user):
    if not order_id:
        raise ServiceError(message="请提供施工单ID", code=400)

    try:
        work_order = WorkOrder.objects.get(id=order_id)
    except WorkOrder.DoesNotExist as exc:
        raise ServiceError(message="施工单不存在", code=404) from exc

    if work_order.approval_status != "pending":
        raise ServiceError(message="只有待审核的订单可以提交审核", code=400)

    approval_steps = MultiLevelApprovalService.start_approval_process(
        work_order, user
    )
    workflow_type = MultiLevelApprovalService.determine_workflow_type(work_order)
    return work_order, approval_steps, workflow_type


def mark_urgent(*, order_id: str, reason: str, user):
    if not order_id:
        raise ServiceError(message="请提供施工单ID", code=400)

    try:
        work_order = WorkOrder.objects.get(id=order_id)
    except WorkOrder.DoesNotExist as exc:
        raise ServiceError(message="施工单不存在", code=404) from exc

    success = UrgentOrderService.mark_as_urgent(
        work_order, reason or "", user
    )
    if not success:
        raise ServiceError(message="标记失败", code=400)

    urgency_level = UrgentOrderService.calculate_urgency_level(work_order)
    return work_order, urgency_level


def get_urgent_orders():
    return UrgentOrderService.get_urgent_orders()


def smart_assign_task(task: WorkOrderTask):
    assignment_service = SmartAssignmentService()
    return assignment_service.smart_assign_single_task(task)


def smart_assign_workorder(workorder: WorkOrder):
    assignment_service = SmartAssignmentService()
    unassigned_tasks = WorkOrderTask.objects.filter(
        workorder=workorder, status__in=["pending", "ready"]
    )

    results = []
    for task in unassigned_tasks:
        result = assignment_service.smart_assign_single_task(task)
        results.append({"task_id": task.id, "task_name": task.task_name, "result": result})

    success_count = sum(1 for result in results if result["result"]["success"])
    return results, success_count
