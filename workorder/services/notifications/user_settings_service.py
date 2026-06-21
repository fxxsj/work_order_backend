"""
用户通知偏好设置服务

管理用户级通知偏好、免打扰时段等设置。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict

from rest_framework import status

from workorder.services.service_errors import ServiceError

logger = logging.getLogger(__name__)


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
