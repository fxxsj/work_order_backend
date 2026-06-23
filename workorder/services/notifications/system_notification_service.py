"""
系统通知服务

提供系统公告、紧急警报、系统级设置与运行状态查询。
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional

from django.contrib.auth.models import User
from django.db.models import Count, Max, Q, QuerySet
from django.utils import timezone
from rest_framework import status

from workorder.services.service_errors import ServiceError

logger = logging.getLogger(__name__)


class SystemNotificationService:
    """系统通知（公告/警报/设置）服务。"""

    @staticmethod
    def list_announcements(
        queryset: QuerySet,
        ordering: str,
        allowed_fields: Iterable[str],
    ) -> List[Dict[str, Any]]:
        """按批次聚合系统公告/紧急警报列表。"""
        rows = list(
            queryset.values(
                "data",
                "notification_type",
                "priority",
                "title",
                "content",
                "expires_at",
            )
            .annotate(
                max_id=Max("id"),
                created_at=Max("created_at"),
                recipient_count=Count("id"),
                read_count=Count("id", filter=Q(is_read=True)),
                sent_count=Count("id", filter=Q(is_sent=True)),
            )
            .order_by()
        )

        reverse = ordering.startswith("-")
        sort_key = ordering.lstrip("-")
        allowed = {field.lstrip("-") for field in allowed_fields}
        if sort_key in allowed:
            rows.sort(key=lambda row: row.get(sort_key) or 0, reverse=reverse)

        return rows

    @staticmethod
    def _build_recipients(
        recipient_ids: Optional[List[int]], only_staff: bool
    ) -> QuerySet:
        """根据筛选条件构建接收者查询集。"""
        recipients = User.objects.all()
        if only_staff:
            recipients = recipients.filter(is_staff=True)
        if recipient_ids:
            recipients = recipients.filter(id__in=recipient_ids)
        return recipients

    @staticmethod
    def create_announcement(
        *,
        title: str,
        content: str,
        recipient_ids: Optional[List[int]] = None,
        only_staff: bool = False,
        expires_in_days: Optional[int] = None,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """创建系统公告。"""
        from workorder.models.system import Notification

        if not title:
            raise ServiceError("缺少 title", code=status.HTTP_400_BAD_REQUEST)
        if not content:
            raise ServiceError(
                "缺少 content", code=status.HTTP_400_BAD_REQUEST
            )
        if priority not in dict(Notification.PRIORITY_CHOICES):
            raise ServiceError(
                "priority 不合法", code=status.HTTP_400_BAD_REQUEST
            )

        recipients = SystemNotificationService._build_recipients(
            recipient_ids, only_staff
        )
        recipient_ids_for_policy = list(
            recipients.values_list("id", flat=True)
        )

        now = timezone.now()
        batch_id = secrets.token_urlsafe(12)
        expires_at = None
        if expires_in_days is not None:
            try:
                days = int(expires_in_days)
                expires_at = now + timedelta(days=days)
            except Exception as e:
                raise ServiceError(
                    "expires_in_days 必须为整数",
                    code=status.HTTP_400_BAD_REQUEST,
                ) from e

        notifications = [
            Notification(
                recipient=recipient,
                notification_type="system",
                priority=priority,
                title=title,
                content=content,
                expires_at=expires_at,
                data={"kind": "announcement", "batch_id": batch_id},
            )
            for recipient in recipients.iterator()
        ]

        Notification.objects.bulk_create(notifications, batch_size=1000)
        Notification.apply_retention_policy(recipient_ids_for_policy)

        return {
            "count": len(notifications),
            "batch_id": batch_id,
        }

    @staticmethod
    def send_urgent_alert(
        *,
        title: str,
        content: str,
        recipient_ids: Optional[List[int]] = None,
        only_staff: bool = False,
    ) -> Dict[str, Any]:
        """发送紧急警报。"""
        from workorder.models.system import Notification

        if not title:
            raise ServiceError("缺少 title", code=status.HTTP_400_BAD_REQUEST)
        if not content:
            raise ServiceError(
                "缺少 content", code=status.HTTP_400_BAD_REQUEST
            )

        recipients = SystemNotificationService._build_recipients(
            recipient_ids, only_staff
        )
        recipient_ids_for_policy = list(
            recipients.values_list("id", flat=True)
        )
        batch_id = secrets.token_urlsafe(12)

        notifications = [
            Notification(
                recipient=recipient,
                notification_type="system",
                priority="urgent",
                title=title,
                content=content,
                data={"kind": "urgent_alert", "batch_id": batch_id},
            )
            for recipient in recipients.iterator()
        ]
        Notification.objects.bulk_create(notifications, batch_size=1000)
        Notification.apply_retention_policy(recipient_ids_for_policy)

        return {
            "count": len(notifications),
            "batch_id": batch_id,
        }

    @staticmethod
    def revoke(batch_id: str) -> int:
        """撤回指定批次的系统通知，返回删除数量。"""
        from workorder.models.system import Notification

        queryset = Notification.objects.filter(
            notification_type="system",
            data__batch_id=str(batch_id),
        )
        deleted_count = queryset.count()
        if deleted_count == 0:
            raise ServiceError("通知不存在", code=status.HTTP_404_NOT_FOUND)
        queryset.delete()
        return deleted_count

    @staticmethod
    def serialize_settings(settings) -> Dict[str, Any]:
        """序列化系统通知设置。"""
        return {
            "websocket_enabled": settings.websocket_enabled,
            "email_enabled": settings.email_enabled,
            "sms_enabled": settings.sms_enabled,
            "email_threshold": settings.email_threshold,
            "notification_retention_days": (
                settings.notification_retention_days
            ),
            "auto_cleanup_enabled": settings.auto_cleanup_enabled,
            "max_notifications_per_user": settings.max_notifications_per_user,
        }

    @staticmethod
    def get_settings() -> Dict[str, Any]:
        """获取系统通知设置。"""
        from workorder.models.system import SystemNotificationSettings

        settings = SystemNotificationSettings.get_solo()
        return SystemNotificationService.serialize_settings(settings)

    @staticmethod
    def update_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
        """更新系统通知设置。"""
        from workorder.models.system import SystemNotificationSettings

        settings = SystemNotificationSettings.get_solo()

        threshold = payload.get("email_threshold", settings.email_threshold)
        valid_thresholds = {
            choice[0]
            for choice in SystemNotificationSettings.EMAIL_THRESHOLD_CHOICES
        }
        if threshold not in valid_thresholds:
            raise ServiceError(
                "email_threshold 不合法",
                code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            retention_days = int(
                payload.get(
                    "notification_retention_days",
                    settings.notification_retention_days,
                )
            )
            max_notifications = int(
                payload.get(
                    "max_notifications_per_user",
                    settings.max_notifications_per_user,
                )
            )
        except (TypeError, ValueError) as e:
            raise ServiceError(
                "通知设置中的数值字段必须为整数",
                code=status.HTTP_400_BAD_REQUEST,
            ) from e

        if retention_days <= 0 or max_notifications <= 0:
            raise ServiceError(
                "通知保留天数和单用户通知上限必须大于 0",
                code=status.HTTP_400_BAD_REQUEST,
            )

        settings.websocket_enabled = bool(
            payload.get("websocket_enabled", settings.websocket_enabled)
        )
        settings.email_enabled = bool(
            payload.get("email_enabled", settings.email_enabled)
        )
        settings.sms_enabled = bool(
            payload.get("sms_enabled", settings.sms_enabled)
        )
        settings.email_threshold = threshold
        settings.notification_retention_days = retention_days
        settings.auto_cleanup_enabled = bool(
            payload.get("auto_cleanup_enabled", settings.auto_cleanup_enabled)
        )
        settings.max_notifications_per_user = max_notifications
        settings.save()

        return SystemNotificationService.serialize_settings(settings)

    @staticmethod
    def system_status() -> Dict[str, Any]:
        """获取通知系统运行状态。"""
        from workorder.models.system import Notification

        try:
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
        except Exception as e:
            raise ServiceError(
                "通知系统异常",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                data={
                    "status": "error",
                    "timestamp": timezone.now().isoformat(),
                    "detail": str(e),
                },
            ) from e

        unsent_notifications = Notification.objects.filter(
            is_sent=False
        ).count()
        recent_notifications = Notification.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count()

        return {
            "status": "healthy",
            "active_connections": 0,
            "unsent_notifications": unsent_notifications,
            "recent_notifications": recent_notifications,
            "channel_layer_type": str(type(channel_layer).__name__),
            "timestamp": timezone.now().isoformat(),
        }
