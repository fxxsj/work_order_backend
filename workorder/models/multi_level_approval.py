"""
多级审核模型

包含审核工作流、审核步骤、审核规则等模型定义
"""

import json

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .core import WorkOrder
from .system import WorkOrderApprovalLog
from .base import TimeStampedModel


class ApprovalWorkflow(TimeStampedModel, models.Model):
    """审核工作流模板"""

    WORKFLOW_TYPES = [
        ("simple", "简单审核"),
        ("standard", "标准审核"),
        ("complex", "复杂审核"),
        ("urgent", "紧急审核"),
    ]

    name = models.CharField("工作流名称", max_length=100)
    workflow_type = models.CharField(
        "工作流类型", max_length=20, choices=WORKFLOW_TYPES
    )
    description = models.TextField("描述", blank=True)
    steps = models.JSONField("审核步骤配置", default=dict)
    is_active = models.BooleanField("是否激活", default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="创建人", null=True, blank=True
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "approval_workflow"
        verbose_name = "审核工作流"
        verbose_name_plural = "审核工作流"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_workflow_type_display()})"


class ApprovalStep(TimeStampedModel, models.Model):
    """审核步骤"""

    STATUS_CHOICES = [
        ("pending", "待审核"),
        ("in_progress", "审核中"),
        ("completed", "已完成"),
        ("skipped", "已跳过"),
    ]

    DECISION_CHOICES = [
        ("approve", "通过"),
        ("reject", "拒绝"),
        ("escalate", "上报"),
    ]

    work_order = models.ForeignKey(
        "WorkOrder",
        on_delete=models.CASCADE,
        verbose_name="施工单",
        related_name="approval_steps",
    )
    workflow = models.ForeignKey(
        ApprovalWorkflow, on_delete=models.CASCADE, verbose_name="工作流"
    )
    step_name = models.CharField("步骤名称", max_length=100)
    step_order = models.IntegerField("步骤顺序")
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="分配给",
        related_name="assigned_approval_steps",
    )
    status = models.CharField(
        "状态", max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    decision = models.CharField(
        "审核决定", max_length=20, choices=DECISION_CHOICES, blank=True
    )
    comments = models.TextField("审核意见", blank=True)
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    completed_at = models.DateTimeField("完成时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "approval_step"
        verbose_name = "审核步骤"
        verbose_name_plural = "审核步骤"
        ordering = ["work_order", "step_order"]
        unique_together = ["work_order", "step_order"]

    def __str__(self):
        return f"{self.work_order.order_number} - {self.step_name}"


class ApprovalRule(TimeStampedModel, models.Model):
    """审核规则"""

    RULE_TYPES = [
        ("value_based", "基于价值"),
        ("time_based", "基于时间"),
        ("customer_based", "基于客户"),
        ("product_based", "基于产品"),
        ("department_based", "基于部门"),
    ]

    name = models.CharField("规则名称", max_length=100, default="默认规则")
    rule_type = models.CharField(
        "规则类型", max_length=20, choices=RULE_TYPES, default="value_based"
    )
    conditions = models.JSONField("触发条件", default=dict)
    workflow_type = models.CharField(
        "工作流类型",
        max_length=20,
        choices=ApprovalWorkflow.WORKFLOW_TYPES,
        default="standard",
    )
    is_active = models.BooleanField("是否激活", default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="创建人", null=True, blank=True
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "approval_rule"
        verbose_name = "审核规则"
        verbose_name_plural = "审核规则"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"


class ApprovalEscalation(TimeStampedModel, models.Model):
    """审核上报"""

    STATUS_CHOICES = [
        ("pending", "待处理"),
        ("approved", "已批准"),
        ("rejected", "已拒绝"),
    ]

    work_order = models.ForeignKey(
        "WorkOrder",
        on_delete=models.CASCADE,
        verbose_name="施工单",
        related_name="approval_escalations",
    )
    from_step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.CASCADE,
        verbose_name="原步骤",
        related_name="escalations_from",
    )
    to_step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="目标步骤",
        related_name="escalations_to",
    )
    escalation_reason = models.TextField("上报原因")
    status = models.CharField(
        "状态", max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    escalated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="上报人",
        related_name="escalated_approvals",
    )
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="处理人",
        related_name="resolved_approvals",
    )
    resolution_comments = models.TextField("处理意见", blank=True)
    resolved_at = models.DateTimeField("处理时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "approval_escalation"
        verbose_name = "审核上报"
        verbose_name_plural = "审核上报"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.work_order.order_number} - 上报"


