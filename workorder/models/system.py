"""
系统相关模型

包含系统管理相关模型：
- UserProfile: 用户扩展信息
- WorkOrderApprovalLog: 施工单审核历史记录
- Notification: 系统通知
- TaskAssignmentRule: 任务分派规则配置
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .base import Department, TimeStampedModel


def default_user_notification_preferences():
    return {
        "email_notifications": True,
        "websocket_notifications": True,
        "task_assignments": True,
        "process_completions": True,
        "deadline_warnings": True,
        "system_announcements": True,
        "urgency_threshold": "normal",
        "quiet_hours_enabled": False,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    }


def default_notification_template_definitions():
    return {
        "workorder_created": {
            "title": "施工单已创建",
            "message": "施工单 {workorder_number} 已成功创建",
            "variables": ["workorder_number", "customer", "total_amount"],
        },
        "workorder_updated": {
            "title": "施工单信息更新",
            "message": "施工单 {workorder_number} 的信息已更新",
            "variables": ["workorder_number", "updated_fields", "updated_by"],
        },
        "workorder_completed": {
            "title": "施工单已完成",
            "message": "施工单 {workorder_number} 已完成",
            "variables": ["workorder_number", "customer"],
        },
        "task_assigned": {
            "title": "新任务分配",
            "message": "您有新的任务: {task_name}",
            "variables": ["task_name", "workorder_number", "assigned_by"],
        },
        "task_started": {
            "title": "任务开始执行",
            "message": "任务 {task_name} 已开始执行",
            "variables": ["task_name", "workorder_number", "assigned_to"],
        },
        "task_completed": {
            "title": "任务完成",
            "message": '任务 "{task_name}" 已完成',
            "variables": ["task_name", "workorder_number", "completed_by"],
        },
        "task_overdue": {
            "title": "任务逾期警告",
            "message": "任务 {task_name} 已逾期",
            "variables": [
                "task_name",
                "workorder_number",
                "deadline",
                "assigned_to",
            ],
        },
        "task_cancelled": {
            "title": "任务已取消",
            "message": '任务 "{task_name}" 已被取消',
            "variables": [
                "task_name",
                "workorder_number",
                "cancellation_reason",
            ],
        },
        "process_completed": {
            "title": "工序完成",
            "message": "工序 {process_name} 已完成",
            "variables": ["process_name", "workorder_number", "completed_by"],
        },
        "approval_requested": {
            "title": "施工单待审核",
            "message": "施工单 {workorder_number} 待审核",
            "variables": [
                "workorder_number",
                "customer",
                "total_amount",
                "comment",
            ],
        },
        "approval_passed": {
            "title": "施工单已审核通过",
            "message": "施工单 {workorder_number} 已审核通过",
            "variables": [
                "workorder_number",
                "dispatched_count",
                "approved_by",
            ],
        },
        "approval_rejected": {
            "title": "施工单审核被拒绝",
            "message": "施工单 {workorder_number} 审核被拒绝",
            "variables": ["workorder_number", "reason", "approved_by"],
        },
        "reapproval_requested": {
            "title": "施工单请求重新审核",
            "message": "施工单 {workorder_number} 已请求重新审核",
            "variables": [
                "workorder_number",
                "reason",
                "requested_by",
                "recipient_role",
            ],
        },
        "workorder_approved": {
            "title": "施工单审核通过",
            "message": "您的施工单 {workorder_number} 已审核通过",
            "variables": ["workorder_number", "approved_by"],
        },
        "workorder_rejected": {
            "title": "施工单审核拒绝",
            "message": "您的施工单 {workorder_number} 已被拒绝",
            "variables": ["workorder_number", "approved_by"],
        },
        "deadline_warning": {
            "title": "交货期预警",
            "message": "施工单 {workorder_number} 将在 {days_remaining} 天后到期",
            "variables": ["workorder_number", "deadline", "days_remaining"],
        },
        "urgent_order": {
            "title": "紧急订单警报",
            "message": "紧急订单 {workorder_number} 需要立即处理",
            "variables": ["workorder_number"],
        },
        "system_announcement": {
            "title": "{title}",
            "message": "{message}",
            "variables": ["title", "message"],
        },
    }


class UserProfile(TimeStampedModel, models.Model):
    """用户扩展信息"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="用户",
    )
    departments = models.ManyToManyField(
        Department,
        blank=True,
        verbose_name="所属部门",
        help_text="用户所属的部门（可多选）",
    )
    notification_preferences = models.JSONField(
        "通知偏好设置",
        default=default_user_notification_preferences,
        blank=True,
        help_text="用户级通知开关、紧急阈值和免打扰时间段配置",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "用户扩展信息"
        verbose_name_plural = "用户扩展信息管理"

    def __str__(self):
        if self.pk and self.departments.exists():
            dept_names = ", ".join(
                [dept.name for dept in self.departments.all()]
            )
            return f"{self.user.username} - {dept_names}"
        return f"{self.user.username} - 未分配部门"


class SystemNotificationSettings(TimeStampedModel, models.Model):
    """系统级通知设置"""

    EMAIL_THRESHOLD_CHOICES = [
        ("low", "低"),
        ("normal", "普通"),
        ("high", "高"),
        ("urgent", "紧急"),
    ]

    singleton_key = models.CharField(
        "单例键",
        max_length=32,
        default="default",
        unique=True,
        editable=False,
    )
    websocket_enabled = models.BooleanField(
        "启用 WebSocket 通知", default=True
    )
    email_enabled = models.BooleanField("启用邮件通知", default=True)
    sms_enabled = models.BooleanField("启用短信通知", default=False)
    email_threshold = models.CharField(
        "邮件发送阈值",
        max_length=10,
        choices=EMAIL_THRESHOLD_CHOICES,
        default="high",
    )
    notification_retention_days = models.PositiveIntegerField(
        "通知保留天数",
        default=30,
    )
    auto_cleanup_enabled = models.BooleanField(
        "自动清理过期通知", default=True
    )
    max_notifications_per_user = models.PositiveIntegerField(
        "单用户通知上限",
        default=1000,
    )

    class Meta:
        verbose_name = "系统通知设置"
        verbose_name_plural = "系统通知设置"

    def __str__(self):
        return "系统通知设置"

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(singleton_key="default")
        return settings


class ApprovalConfig(TimeStampedModel, models.Model):
    """模块级审核开关配置（单例）

    控制每个业务模块是否开启审核流程。关闭后该模块提交即由系统
    自动通过并留痕，无需审核人介入；开启后走原有审批流程。

    所有开关默认 True，保证上线后行为与现状完全一致（零回归）。
    """

    # model._meta.model_name -> 配置字段名，统一通过 is_enabled() 查询
    MODULE_FIELD_MAP = {
        "workorder": "workorder_approval_enabled",
        "salesorder": "salesorder_approval_enabled",
        "purchaseorder": "purchaseorder_approval_enabled",
        "invoice": "invoice_approval_enabled",
        "supplierpayment": "supplierpayment_approval_enabled",
        "stockin": "stockin_approval_enabled",
        "stockout": "stockout_approval_enabled",
    }

    singleton_key = models.CharField(
        "单例键",
        max_length=32,
        default="default",
        unique=True,
        editable=False,
    )
    workorder_approval_enabled = models.BooleanField(
        "施工单审核", default=True
    )
    salesorder_approval_enabled = models.BooleanField(
        "客户订单审核", default=True
    )
    purchaseorder_approval_enabled = models.BooleanField(
        "采购单审核", default=True
    )
    invoice_approval_enabled = models.BooleanField("发票审核", default=True)
    supplierpayment_approval_enabled = models.BooleanField(
        "供应商付款审核", default=True
    )
    stockin_approval_enabled = models.BooleanField("入库单审核", default=True)
    stockout_approval_enabled = models.BooleanField(
        "出库单审核", default=True
    )

    class Meta:
        verbose_name = "审核开关设置"
        verbose_name_plural = "审核开关设置"

    def __str__(self):
        return "审核开关设置"

    @classmethod
    def get_solo(cls):
        config, _ = cls.objects.get_or_create(singleton_key="default")
        return config

    def is_enabled(self, model_name: str) -> bool:
        """指定模块是否开启审核。未知模块默认开启（保守策略）。"""
        field = self.MODULE_FIELD_MAP.get(model_name)
        if field is None:
            return True
        return getattr(self, field, True)


class NotificationTemplate(TimeStampedModel, models.Model):
    """通知模板"""

    key = models.CharField("模板键", max_length=50, unique=True)
    title = models.CharField("标题模板", max_length=200)
    message = models.TextField("内容模板")
    variables = models.JSONField("模板变量", default=list, blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "通知模板"
        verbose_name_plural = "通知模板"
        ordering = ["key"]

    def __str__(self):
        return self.key

    @classmethod
    def seed_defaults(cls):
        for key, config in default_notification_template_definitions().items():
            cls.objects.get_or_create(
                key=key,
                defaults={
                    "title": config["title"],
                    "message": config["message"],
                    "variables": config["variables"],
                    "is_active": True,
                },
            )
        return cls.objects.order_by("key")

    @classmethod
    def render(cls, key, variables=None):
        variables = variables or {}
        cls.seed_defaults()
        template = cls.objects.filter(key=key, is_active=True).first()
        if template is None:
            return None

        safe_variables = {
            field: "" if value is None else str(value)
            for field, value in variables.items()
        }

        class _SafeDict(dict):
            def __missing__(self, field):
                return "{" + field + "}"

        return {
            "key": template.key,
            "title": template.title.format_map(_SafeDict(safe_variables)),
            "message": template.message.format_map(_SafeDict(safe_variables)),
            "variables": template.variables,
        }

    @classmethod
    def render_with_fallback(cls, key, variables=None, title="", message=""):
        rendered = cls.render(key, variables)
        if rendered:
            return rendered["title"], rendered["message"]
        return title, message


class WorkOrderApprovalLog(models.Model):
    """施工单审核历史记录"""

    work_order = models.ForeignKey(
        "workorder.WorkOrder",
        on_delete=models.CASCADE,
        related_name="approval_logs",
        verbose_name="施工单",
    )
    APPROVAL_STATUS_CHOICES = [
        ("draft", "草稿"),
        ("submitted", "待审核"),
        ("approved", "已审核"),
        ("rejected", "已拒绝"),
    ]
    approval_status = models.CharField(
        "审核状态", max_length=20, choices=APPROVAL_STATUS_CHOICES
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_logs",
        verbose_name="审核人",
    )
    approved_at = models.DateTimeField("审核时间", auto_now_add=True)
    approval_comment = models.TextField(
        "审核意见", blank=True, help_text="审核意见或说明"
    )
    rejection_reason = models.TextField(
        "拒绝原因", blank=True, help_text="审核拒绝时的拒绝原因"
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "施工单审核历史"
        verbose_name_plural = "施工单审核历史管理"
        ordering = ["-approved_at", "-created_at"]

    def __str__(self):
        status_display = dict(self.APPROVAL_STATUS_CHOICES).get(
            self.approval_status, self.approval_status
        )
        return (
            f"{self.work_order.order_number} - {status_display} - "
            f"{self.approved_by.username if self.approved_by else '未知'}"
        )


class Notification(models.Model):
    """系统通知"""

    NOTIFICATION_TYPE_CHOICES = [
        ("workorder_created", "施工单创建"),
        ("workorder_updated", "施工单更新"),
        ("approval_passed", "审核通过"),
        ("approval_rejected", "审核拒绝"),
        ("approval_requested", "请求审核"),
        ("reapproval_requested", "请求重新审核"),
        ("task_assigned", "任务分派"),
        ("task_started", "任务开始"),
        ("task_overdue", "任务逾期"),
        ("task_due_soon", "任务即将到期"),
        ("process_completed", "工序完成"),
        ("workorder_completed", "施工单完成"),
        ("task_cancelled", "任务取消"),
        ("purchase_order_submitted", "采购单待审核"),
        ("purchase_order_approved", "采购单已批准"),
        ("purchase_order_rejected", "采购单已拒绝"),
        ("purchase_order_received", "采购单已收货"),
        ("low_stock_warning", "库存不足预警"),
        ("system", "系统通知"),
    ]

    PRIORITY_CHOICES = [
        ("low", "低"),
        ("normal", "普通"),
        ("high", "高"),
        ("urgent", "紧急"),
    ]

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="接收人",
    )
    notification_type = models.CharField(
        "通知类型", max_length=30, choices=NOTIFICATION_TYPE_CHOICES
    )
    title = models.CharField("标题", max_length=200)
    content = models.TextField("内容", help_text="通知详细内容")
    priority = models.CharField(
        "优先级", max_length=10, choices=PRIORITY_CHOICES, default="normal"
    )

    # 关联对象（可选，用于跳转到相关页面）
    work_order = models.ForeignKey(
        "workorder.WorkOrder",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="关联施工单",
    )
    work_order_process = models.ForeignKey(
        "workorder.WorkOrderProcess",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="关联工序",
    )
    task = models.ForeignKey(
        "workorder.WorkOrderTask",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="关联任务",
    )
    purchase_order = models.ForeignKey(
        "workorder.PurchaseOrder",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="关联采购单",
    )

    # 通知状态
    is_read = models.BooleanField("已读", default=False)
    read_at = models.DateTimeField("阅读时间", null=True, blank=True)
    is_sent = models.BooleanField("已发送", default=False)

    # 元数据
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    expires_at = models.DateTimeField(
        "过期时间",
        null=True,
        blank=True,
        help_text="通知过期时间，过期后不再显示",
    )
    data = models.JSONField("扩展数据", null=True, blank=True)

    class Meta:
        verbose_name = "系统通知"
        verbose_name_plural = "系统通知管理"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
            models.Index(fields=["notification_type", "-created_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient.username} - {self.title}"

    def mark_as_read(self):
        """标记为已读"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    @classmethod
    def create_notification(
        cls,
        recipient,
        notification_type,
        title,
        content,
        priority="normal",
        work_order=None,
        work_order_process=None,
        task=None,
        expires_at=None,
        template_key=None,
        template_variables=None,
        purchase_order=None,
    ):
        """创建通知的便捷方法"""
        if template_key:
            title, content = NotificationTemplate.render_with_fallback(
                template_key,
                template_variables,
                title=title,
                message=content,
            )
        return cls.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            content=content,
            priority=priority,
            work_order=work_order,
            work_order_process=work_order_process,
            task=task,
            expires_at=expires_at,
            purchase_order=purchase_order,
        )

    @classmethod
    def apply_retention_policy(cls, user_ids=None):
        settings = SystemNotificationSettings.get_solo()
        queryset = cls.objects.all()
        if user_ids:
            queryset = queryset.filter(recipient_id__in=user_ids)

        if settings.auto_cleanup_enabled:
            expiry_cutoff = timezone.now() - timedelta(
                days=settings.notification_retention_days
            )
            queryset.filter(created_at__lt=expiry_cutoff).delete()
            queryset.filter(
                expires_at__isnull=False, expires_at__lt=timezone.now()
            ).delete()

        max_count = settings.max_notifications_per_user
        recipient_ids = (
            user_ids
            or queryset.values_list("recipient_id", flat=True).distinct()
        )
        for recipient_id in recipient_ids:
            stale_ids = list(
                cls.objects.filter(recipient_id=recipient_id)
                .order_by("-created_at")
                .values_list("id", flat=True)[max_count:]
            )
            if stale_ids:
                cls.objects.filter(id__in=stale_ids).delete()


class TaskAssignmentRule(TimeStampedModel, models.Model):
    """任务分派规则配置"""

    OPERATOR_SELECTION_STRATEGY_CHOICES = [
        ("least_tasks", "任务数量最少（工作量均衡）"),
        ("random", "随机选择"),
        ("round_robin", "轮询分配"),
        ("first_available", "第一个可用"),
    ]

    process = models.ForeignKey(
        "workorder.Process",
        on_delete=models.CASCADE,
        related_name="assignment_rules",
        verbose_name="工序",
        help_text="该规则适用的工序",
    )
    department = models.ForeignKey(
        "workorder.Department",
        on_delete=models.CASCADE,
        related_name="assignment_rules",
        verbose_name="分派部门",
        help_text="该工序应分派到的部门",
    )
    priority = models.IntegerField(
        "优先级", default=0, help_text="优先级越高越优先匹配（0-100）"
    )
    operator_selection_strategy = models.CharField(
        "操作员选择策略",
        max_length=20,
        choices=OPERATOR_SELECTION_STRATEGY_CHOICES,
        default="least_tasks",
        help_text="从部门中选择操作员的策略",
    )
    is_active = models.BooleanField(
        "是否启用", default=True, help_text="是否启用该规则"
    )
    notes = models.TextField("备注", blank=True, help_text="规则说明或备注")

    class Meta:
        verbose_name = "任务分派规则"
        verbose_name_plural = "任务分派规则管理"
        ordering = ["process", "-priority", "department"]
        unique_together = [
            ["process", "department"]
        ]  # 同一工序同一部门只能有一条规则

    def __str__(self):
        return (
            f"{self.process.name} -> {self.department.name} "
            f"(优先级:{self.priority})"
        )
