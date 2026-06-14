"""
通知业务服务

将 notification.py 视图集中的业务逻辑下沉到服务层：
- NotificationService：用户通知的已读/删除/统计/票据
- SystemNotificationService：系统公告/紧急警报/系统设置/状态
- UserNotificationSettingsService：用户级通知偏好设置
- NotificationTemplateService：通知模板管理

视图层只负责参数提取、调用服务和格式化响应。
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Max, Q, QuerySet
from django.utils import timezone
from rest_framework import status

from workorder.services.service_errors import ServiceError

logger = logging.getLogger(__name__)


class NotificationService:
    """用户通知服务。"""

    @staticmethod
    def mark_read(notification) -> None:
        """标记单条通知为已读。"""
        notification.mark_as_read()

    @staticmethod
    def mark_all_read(queryset: QuerySet) -> int:
        """批量标记当前查询集内所有通知为已读，返回更新数量。"""
        count = queryset.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
        )
        return count

    @staticmethod
    def delete(notification) -> None:
        """删除单条通知。"""
        notification.delete()

    @staticmethod
    def delete_all_read(queryset: QuerySet) -> int:
        """删除查询集内所有已读通知，返回删除数量。"""
        count = queryset.filter(is_read=True).delete()[0]
        return count

    @staticmethod
    def unread_count(queryset: QuerySet) -> int:
        """未读通知数量。"""
        return queryset.filter(is_read=False).count()

    @staticmethod
    def statistics(queryset: QuerySet) -> Dict[str, int]:
        """通知统计。"""
        return {
            "total_count": queryset.count(),
            "unread_count": queryset.filter(is_read=False).count(),
            "read_count": queryset.filter(is_read=True).count(),
            "urgent_count": queryset.filter(priority="urgent").count(),
            "high_count": queryset.filter(priority="high").count(),
        }

    @staticmethod
    def ws_ticket(user_id: int) -> Dict[str, Any]:
        """生成一次性 WebSocket 连接票据。"""
        ticket = secrets.token_urlsafe(32)
        cache.set(f"ws_ticket:{ticket}", user_id, timeout=60)
        return {"ticket": ticket, "expires_in": 60}


class SystemNotificationService:
    """系统通知（公告/警报/设置）服务。"""

    @staticmethod
    def list_announcements(queryset: QuerySet, ordering: str, allowed_fields: Iterable[str]) -> List[Dict[str, Any]]:
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
    def _build_recipients(recipient_ids: Optional[List[int]], only_staff: bool) -> QuerySet:
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
            raise ServiceError("缺少 content", code=status.HTTP_400_BAD_REQUEST)
        if priority not in dict(Notification.PRIORITY_CHOICES):
            raise ServiceError("priority 不合法", code=status.HTTP_400_BAD_REQUEST)

        recipients = SystemNotificationService._build_recipients(recipient_ids, only_staff)
        recipient_ids_for_policy = list(recipients.values_list("id", flat=True))

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
            raise ServiceError("缺少 content", code=status.HTTP_400_BAD_REQUEST)

        recipients = SystemNotificationService._build_recipients(recipient_ids, only_staff)
        recipient_ids_for_policy = list(recipients.values_list("id", flat=True))
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
            "notification_retention_days": settings.notification_retention_days,
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
            choice[0] for choice in SystemNotificationSettings.EMAIL_THRESHOLD_CHOICES
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
        settings.sms_enabled = bool(payload.get("sms_enabled", settings.sms_enabled))
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

        unsent_notifications = Notification.objects.filter(is_sent=False).count()
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


class UserNotificationSettingsService:
    """用户通知偏好设置服务。"""

    @staticmethod
    def _get_profile(user) -> Any:
        """获取或初始化用户扩展信息。"""
        from workorder.models.system import (
            UserProfile,
            default_user_notification_preferences,
        )

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not profile.notification_preferences:
            profile.notification_preferences = default_user_notification_preferences()
            profile.save(update_fields=["notification_preferences", "updated_at"])
        return profile

    @staticmethod
    def _serialize_preferences(profile) -> Dict[str, Any]:
        from workorder.models.system import default_user_notification_preferences

        prefs = default_user_notification_preferences()
        prefs.update(profile.notification_preferences or {})
        prefs["user_id"] = profile.user_id
        return prefs

    @staticmethod
    def _validate_time_text(value: str, field_name: str) -> None:
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
            raise ServiceError(
                f"{field_name} 必须为 HH:MM 格式",
                code=status.HTTP_400_BAD_REQUEST,
            )

    @staticmethod
    def get_settings(user) -> Dict[str, Any]:
        """获取用户通知设置。"""
        profile = UserNotificationSettingsService._get_profile(user)
        return UserNotificationSettingsService._serialize_preferences(profile)

    @staticmethod
    def update_settings(user, payload: Dict[str, Any]) -> Dict[str, Any]:
        """更新用户通知设置。"""
        from workorder.models.system import default_user_notification_preferences

        profile = UserNotificationSettingsService._get_profile(user)
        current = default_user_notification_preferences()
        current.update(profile.notification_preferences or {})

        urgency_threshold = (
            payload.get("urgency_threshold", current["urgency_threshold"]) or "normal"
        ).strip()
        if urgency_threshold not in {"low", "normal", "high", "urgent"}:
            raise ServiceError(
                "urgency_threshold 不合法",
                code=status.HTTP_400_BAD_REQUEST,
            )

        quiet_start = (
            payload.get("quiet_hours_start", current["quiet_hours_start"]) or "22:00"
        ).strip()
        quiet_end = (
            payload.get("quiet_hours_end", current["quiet_hours_end"]) or "08:00"
        ).strip()
        UserNotificationSettingsService._validate_time_text(quiet_start, "quiet_hours_start")
        UserNotificationSettingsService._validate_time_text(quiet_end, "quiet_hours_end")

        settings_data = {
            "email_notifications": bool(
                payload.get("email_notifications", current["email_notifications"])
            ),
            "websocket_notifications": bool(
                payload.get(
                    "websocket_notifications", current["websocket_notifications"]
                )
            ),
            "task_assignments": bool(
                payload.get("task_assignments", current["task_assignments"])
            ),
            "process_completions": bool(
                payload.get("process_completions", current["process_completions"])
            ),
            "deadline_warnings": bool(
                payload.get("deadline_warnings", current["deadline_warnings"])
            ),
            "system_announcements": bool(
                payload.get("system_announcements", current["system_announcements"])
            ),
            "urgency_threshold": urgency_threshold,
            "quiet_hours_enabled": bool(
                payload.get("quiet_hours_enabled", current["quiet_hours_enabled"])
            ),
            "quiet_hours_start": quiet_start,
            "quiet_hours_end": quiet_end,
        }

        profile.notification_preferences = settings_data
        profile.save(update_fields=["notification_preferences", "updated_at"])

        return UserNotificationSettingsService._serialize_preferences(profile)

    @staticmethod
    def get_notification_preferences() -> Dict[str, Any]:
        """返回默认通知偏好元数据。"""
        return {
            "task_assigned": {
                "label": "任务分配",
                "description": "当有新任务分配给您时通知",
                "enabled": True,
                "channels": ["websocket", "in_app"],
            },
            "process_completed": {
                "label": "工序完成",
                "description": "当相关工序完成时通知",
                "enabled": True,
                "channels": ["websocket", "in_app"],
            },
            "workorder_approved": {
                "label": "施工单审核",
                "description": "当施工单审核结果出来时通知",
                "enabled": True,
                "channels": ["websocket", "in_app", "email"],
            },
            "deadline_warning": {
                "label": "交货期预警",
                "description": "当施工单接近交货期时通知",
                "enabled": True,
                "channels": ["websocket", "in_app", "email"],
            },
            "system_announcement": {
                "label": "系统公告",
                "description": "系统重要公告通知",
                "enabled": True,
                "channels": ["websocket", "in_app"],
            },
        }


class NotificationTemplateService:
    """通知模板服务。"""

    @staticmethod
    def _serialize_templates() -> Dict[str, Any]:
        from workorder.models.system import NotificationTemplate

        NotificationTemplate.seed_defaults()
        return {
            item.key: {
                "title": item.title,
                "message": item.message,
                "variables": item.variables,
                "is_active": item.is_active,
            }
            for item in NotificationTemplate.objects.order_by("key")
        }

    @staticmethod
    def get_templates() -> Dict[str, Any]:
        """获取所有通知模板。"""
        return NotificationTemplateService._serialize_templates()

    @staticmethod
    def update_template(
        *,
        template_name: str,
        title: Optional[str] = None,
        message: Optional[str] = None,
        variables: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """更新通知模板。"""
        from workorder.models.system import NotificationTemplate

        if not template_name:
            raise ServiceError("缺少 template_name", code=status.HTTP_400_BAD_REQUEST)

        NotificationTemplate.seed_defaults()
        template = NotificationTemplate.objects.filter(key=template_name).first()
        if template is None:
            raise ServiceError("模板不存在", code=status.HTTP_404_NOT_FOUND)

        if title is not None:
            template.title = str(title).strip()
        if message is not None:
            template.message = str(message).strip()
        if variables is not None:
            if not isinstance(variables, list):
                raise ServiceError(
                    "variables 必须为数组",
                    code=status.HTTP_400_BAD_REQUEST,
                )
            template.variables = [str(item) for item in variables]
        if is_active is not None:
            template.is_active = bool(is_active)

        if not template.title or not template.message:
            raise ServiceError(
                "标题和内容不能为空",
                code=status.HTTP_400_BAD_REQUEST,
            )

        template.save()
        return {
            "template_name": template.key,
            "title": template.title,
            "message": template.message,
            "variables": template.variables,
            "is_active": template.is_active,
        }

    @staticmethod
    def preview_template(template_name: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """渲染模板预览。"""
        from workorder.models.system import NotificationTemplate

        if not isinstance(variables, dict):
            raise ServiceError(
                "variables 必须为对象",
                code=status.HTTP_400_BAD_REQUEST,
            )

        rendered = NotificationTemplate.render(template_name, variables)
        if not rendered:
            raise ServiceError("模板不存在", code=status.HTTP_404_NOT_FOUND)

        return {
            "template_name": template_name,
            "title": rendered["title"],
            "message": rendered["message"],
            "variables": variables,
        }
