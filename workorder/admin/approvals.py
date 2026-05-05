"""多级审批管理 Admin。"""

from django.contrib import admin

from ..models import ApprovalEscalation, ApprovalRule, ApprovalStep, ApprovalWorkflow


@admin.register(ApprovalWorkflow)
class ApprovalWorkflowAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "workflow_type",
        "is_active",
        "created_by",
        "updated_at",
    ]
    list_filter = ["workflow_type", "is_active", "created_at", "updated_at"]
    search_fields = ["name", "description", "created_by__username"]
    autocomplete_fields = ["created_by"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-updated_at"]


@admin.register(ApprovalStep)
class ApprovalStepAdmin(admin.ModelAdmin):
    list_display = [
        "work_order",
        "workflow",
        "step_name",
        "step_order",
        "assigned_to",
        "status",
        "decision",
        "updated_at",
    ]
    list_filter = ["status", "decision", "workflow", "created_at"]
    search_fields = [
        "work_order__order_number",
        "workflow__name",
        "step_name",
        "assigned_to__username",
    ]
    autocomplete_fields = ["work_order", "workflow", "assigned_to"]
    readonly_fields = ["created_at", "updated_at", "started_at", "completed_at"]
    ordering = ["-updated_at"]


@admin.register(ApprovalRule)
class ApprovalRuleAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "rule_type",
        "workflow_type",
        "is_active",
        "created_by",
        "updated_at",
    ]
    list_filter = ["rule_type", "workflow_type", "is_active", "created_at"]
    search_fields = ["name", "created_by__username"]
    autocomplete_fields = ["created_by"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-updated_at"]


@admin.register(ApprovalEscalation)
class ApprovalEscalationAdmin(admin.ModelAdmin):
    list_display = [
        "work_order",
        "from_step",
        "to_step",
        "status",
        "escalated_by",
        "resolved_by",
        "created_at",
    ]
    list_filter = ["status", "created_at", "resolved_at"]
    search_fields = [
        "work_order__order_number",
        "from_step__step_name",
        "to_step__step_name",
        "escalated_by__username",
    ]
    autocomplete_fields = ["work_order", "from_step", "to_step", "escalated_by", "resolved_by"]
    readonly_fields = ["created_at", "updated_at", "resolved_at"]
    ordering = ["-created_at"]
