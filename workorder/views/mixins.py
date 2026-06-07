"""
视图集混入类

提供可复用的视图功能模块。
"""

from rest_framework import status
from rest_framework.decorators import action
from workorder.response import APIResponse


class ApprovalTimelineMixin:
    """
    审批时间线混入类

    为需要审核的模型提供 approval_timeline action，
    返回该对象的所有审批历史记录（来自 AuditLog）。
    """

    @action(detail=True, methods=["get"])
    def approval_timeline(self, request, pk=None):
        """获取审批时间线"""
        from django.contrib.contenttypes.models import ContentType
        from workorder.models.audit import AuditLog

        obj = self.get_object()
        ct = ContentType.objects.get_for_model(obj)

        logs = (
            AuditLog.objects.filter(
                content_type=ct,
                object_id=str(obj.pk),
                action_type__in=[
                    AuditLog.ACTION_APPROVE,
                    AuditLog.ACTION_REJECT,
                    AuditLog.ACTION_UPDATE,
                ],
            )
            .select_related("user")
            .order_by("created_at")
        )

        data = [
            {
                "id": str(log.id),
                "action_type": log.action_type,
                "action_display": log.get_action_type_display(),
                "username": log.username,
                "created_at": log.created_at,
                "comment": log.changes.get("comment", ""),
                "approval_status": log.changes.get("approval_status", ""),
            }
            for log in logs
        ]

        return APIResponse.success(data=data)
