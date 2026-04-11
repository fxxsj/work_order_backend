"""
多级审核服务

包含多级审核和紧急订单处理的服务类
"""

from django.utils import timezone
from django.contrib.auth.models import User

from ..models import (
    ApprovalWorkflow,
    ApprovalStep,
    ApprovalEscalation,
    WorkOrder,
    WorkOrderApprovalLog,
)


class MultiLevelApprovalService:
    """多级审核服务类"""

    @classmethod
    def create_default_workflow(cls, workflow_type, user):
        """创建默认工作流"""
        workflow_configs = {
            "simple": {
                "name": "简单审核流程",
                "steps": [
                    {"step_name": "主管审核", "assigned_role": "supervisor"},
                ],
            },
            "standard": {
                "name": "标准审核流程",
                "steps": [
                    {"step_name": "主管审核", "assigned_role": "supervisor"},
                    {"step_name": "经理审核", "assigned_role": "manager"},
                ],
            },
            "complex": {
                "name": "复杂审核流程",
                "steps": [
                    {"step_name": "主管审核", "assigned_role": "supervisor"},
                    {"step_name": "经理审核", "assigned_role": "manager"},
                    {"step_name": "总监审核", "assigned_role": "director"},
                ],
            },
            "urgent": {
                "name": "紧急审核流程",
                "steps": [
                    {"step_name": "紧急处理", "assigned_role": "urgent_handler"},
                ],
            },
        }

        config = workflow_configs.get(workflow_type, workflow_configs["standard"])

        workflow, _ = ApprovalWorkflow.objects.update_or_create(
            workflow_type=workflow_type,
            defaults={
                "name": config["name"],
                "steps": {"steps": config["steps"]},
                "is_active": True,
                "created_by": user,
            },
        )
        return workflow

    @classmethod
    def start_approval_process(cls, work_order, user):
        """启动审核流程"""
        workflow_type = cls.determine_workflow_type(work_order)

        workflow = (
            ApprovalWorkflow.objects.filter(workflow_type=workflow_type)
            .order_by("-created_at")
            .first()
        )
        if not workflow:
            workflow = cls.create_default_workflow(workflow_type, user)

        # 创建审核步骤
        steps_data = workflow.steps or {}
        if isinstance(steps_data, dict):
            steps_config = steps_data.get("steps", [])
        else:
            steps_config = steps_data
        approval_steps = []

        for i, step_data in enumerate(steps_config, 1):
            step = ApprovalStep.objects.create(
                work_order=work_order,
                workflow=workflow,
                step_name=step_data["step_name"],
                step_order=i,
            )
            approval_steps.append(step)

        # 分配第一步给合适的用户
        if approval_steps:
            first_step = approval_steps[0]
            role = cls._get_role_for_step(first_step)
            assigned_user = cls._get_step_assignee(role=role)
            if assigned_user:
                first_step.assigned_to = assigned_user
                first_step.save(update_fields=["assigned_to"])

        return approval_steps

    @classmethod
    def determine_workflow_type(cls, work_order):
        """确定工作流类型"""
        if work_order.priority == "urgent":
            return "urgent"
        # 基于价值判断
        if work_order.total_amount >= 50000:
            return "complex"
        elif work_order.total_amount >= 10000:
            return "standard"
        else:
            return "simple"

    @classmethod
    def complete_approval_step(cls, step, decision, comments, user):
        """完成审核步骤"""
        if step.status != "in_progress":
            return False

        step.decision = decision
        step.comments = comments
        step.completed_at = timezone.now()

        if decision == "escalate":
            step.status = "completed"
            # 创建上报记录
            ApprovalEscalation.objects.create(
                work_order=step.work_order,
                from_step=step,
                escalation_reason=comments or "用户上报",
                escalated_by=user,
            )
        else:
            step.status = "completed"

            # 如果是通过，检查是否还有下一步
            if decision == "approve":
                next_step = ApprovalStep.objects.filter(
                    work_order=step.work_order, step_order=step.step_order + 1
                ).first()

                if next_step:
                    # 分配下一步给合适的用户
                    role = cls._get_role_for_step(next_step)
                    assigned_user = cls._get_step_assignee(role=role)
                    if assigned_user:
                        next_step.assigned_to = assigned_user
                        next_step.status = "pending"
                        next_step.save(update_fields=["assigned_to", "status"])

        step.save(update_fields=["decision", "comments", "completed_at", "status"])
        return True

    @classmethod
    def _get_role_for_step(cls, step):
        """从 workflow.steps 配置中获取当前步骤的角色（best-effort）"""
        steps_data = step.workflow.steps or {}
        if isinstance(steps_data, dict):
            steps_config = steps_data.get("steps", [])
        else:
            steps_config = steps_data

        idx = step.step_order - 1
        if idx < 0 or idx >= len(steps_config):
            return None
        return steps_config[idx].get("assigned_role")

    @classmethod
    def _get_step_assignee(cls, role=None):
        """获取步骤分配对象（按角色匹配 group；找不到则回退到管理员）"""
        if role:
            user = User.objects.filter(is_active=True, groups__name=role).first()
            if user:
                return user

        user = User.objects.filter(is_active=True, is_superuser=True).first()
        if user:
            return user
        return User.objects.filter(is_active=True, is_staff=True).first()


class UrgentOrderService:
    """紧急订单服务类"""

    @classmethod
    def mark_as_urgent(cls, work_order, reason, user):
        """标记为紧急订单"""
        work_order.priority = "urgent"
        work_order.save(update_fields=["priority"])

        # 记录紧急标记日志
        WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            action_type="mark_urgent",
            action_by=user,
            comments=reason,
        )

        return True

    @classmethod
    def calculate_urgency_level(cls, work_order):
        """计算紧急程度"""
        urgency_level = 1

        if work_order.priority == "urgent":
            urgency_level += 3

        # 检查是否即将到期
        if work_order.deadline:
            days_remaining = (work_order.deadline - timezone.now().date()).days
            if days_remaining <= 1:
                urgency_level += 2
            elif days_remaining <= 3:
                urgency_level += 1

        return min(urgency_level, 5)  # 最高5级

    @classmethod
    def get_urgent_orders(cls):
        """获取紧急订单列表"""
        urgent_orders = (
            WorkOrder.objects.filter(
                priority="urgent", status__in=["pending", "in_progress"]
            )
            .select_related("customer", "created_by")
            .order_by("-priority", "deadline")
        )

        return [
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer_name": order.customer.name if order.customer else "",
                "priority": order.priority,
                "urgency_level": cls.calculate_urgency_level(order),
                "deadline": order.deadline,
                "created_at": order.created_at,
            }
            for order in urgent_orders
        ]