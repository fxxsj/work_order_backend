"""
系统管理视图集

包含审核日志、通知、任务分派规则等系统管理视图集。
"""

from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from workorder.response import APIResponse
from workorder.docs.system import (
    notification_docs,
    notification_mark_all_docs,
    notification_mark_read_docs,
    notification_unread_docs,
    task_assignment_global_state_docs,
    task_assignment_preview_docs,
    task_assignment_rule_docs,
    task_assignment_set_state_docs,
)

from ..models.system import Notification, TaskAssignmentRule
from ..serializers.system import NotificationSerializer, TaskAssignmentRuleSerializer
from .base_viewsets import BaseViewSet


@notification_docs
class NotificationViewSet(viewsets.ModelViewSet):
    """通知视图集"""

    queryset = Notification.objects.all()  # 默认 queryset，会被 get_queryset() 覆盖
    serializer_class = NotificationSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = [
        "notification_type",
        "priority",
        "is_read",
        "work_order",
        "task",
    ]
    ordering_fields = ["created_at", "priority"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """只返回当前用户的通知"""
        queryset = Notification.objects.filter(recipient=self.request.user)
        # 过滤过期通知
        queryset = queryset.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )
        return queryset.select_related(
            "work_order", "work_order_process", "task", "recipient"
        )

    @action(detail=True, methods=["post"])
    @notification_mark_read_docs
    def mark_read(self, request, pk=None):
        """标记通知为已读"""
        notification = self.get_object()
        notification.mark_as_read()
        serializer = self.get_serializer(notification)
        return APIResponse.success(data=serializer.data)

    @action(detail=False, methods=["post"])
    @notification_mark_all_docs
    def mark_all_read(self, request):
        """标记所有通知为已读"""
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return APIResponse.success(message=f"已标记 {count} 条通知为已读")

    @action(detail=False, methods=["get"])
    @notification_unread_docs
    def unread_count(self, request):
        """获取未读通知数量"""
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return APIResponse.success(data={"unread_count": count})


# ==================== 采购管理视图集 ====================


@task_assignment_rule_docs
class TaskAssignmentRuleViewSet(BaseViewSet):
    """任务分派规则视图集"""

    queryset = TaskAssignmentRule.objects.select_related("process", "department").all()
    serializer_class = TaskAssignmentRuleSerializer
    filterset_fields = ["process", "department", "is_active"]
    search_fields = [
        "process__name",
        "process__code",
        "department__name",
        "department__code",
        "notes",
    ]
    ordering_fields = ["priority", "created_at", "updated_at"]
    ordering = ["process", "-priority", "department"]

    @action(detail=False, methods=["get"])
    @task_assignment_preview_docs
    def preview(self, request):
        """生成分派预览

        返回所有活跃工序的分派预览，显示每个工序将分派到哪个部门
        """
        from ..services.dispatch_service import (
            AutoDispatchService,
            DispatchPreviewService,
        )

        preview_data = DispatchPreviewService.generate_preview()

        return APIResponse.success(
            data={
                "preview": preview_data,
                "global_enabled": AutoDispatchService.is_global_dispatch_enabled(),
                "generated_at": timezone.now().isoformat(),
            }
        )

    @action(detail=False, methods=["get"])
    @task_assignment_global_state_docs
    def global_state(self, request):
        """获取全局自动分派启用状态"""
        from ..services.dispatch_service import AutoDispatchService

        enabled = AutoDispatchService.is_global_dispatch_enabled()
        return APIResponse.success(data={"enabled": enabled})

    @action(detail=False, methods=["post"])
    @task_assignment_set_state_docs
    def set_global_state(self, request):
        """设置全局自动分派启用状态

        Body:
            enabled (bool): True 启用，False 禁用
        """
        from ..services.dispatch_service import AutoDispatchService

        enabled = request.data.get("enabled", False)
        new_state = AutoDispatchService.set_global_dispatch_enabled(enabled)
        return APIResponse.success(data={"enabled": new_state})
