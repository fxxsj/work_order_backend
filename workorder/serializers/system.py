"""
系统管理序列化器模块

包含通知、审核日志、任务分派规则等系统管理的序列化器。
"""

from rest_framework import serializers
from ..models.system import WorkOrderApprovalLog, Notification, TaskAssignmentRule


class WorkOrderApprovalLogSerializer(serializers.ModelSerializer):
    """施工单审核历史序列化器"""
    approval_status_display = serializers.CharField(source='get_approval_status_display', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, allow_null=True)

    class Meta:
        model = WorkOrderApprovalLog
        fields = '__all__'


class NotificationSerializer(serializers.ModelSerializer):
    """通知序列化器"""
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    recipient_name = serializers.CharField(source='recipient.username', read_only=True)
    work_order_number = serializers.CharField(source='work_order.order_number', read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['created_at', 'read_at']


class TaskAssignmentRuleSerializer(serializers.ModelSerializer):
    """任务分派规则序列化器"""
    process_name = serializers.CharField(source='process.name', read_only=True)
    process_code = serializers.CharField(source='process.code', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    operator_selection_strategy_display = serializers.CharField(
        source='get_operator_selection_strategy_display', read_only=True
    )

    class Meta:
        model = TaskAssignmentRule
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
