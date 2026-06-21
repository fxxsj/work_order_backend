"""
通知服务包

将原先 `workorder.services.notification_service` 中的四个服务类拆分到独立模块，
便于维护并降低单文件复杂度。
"""

from .system_notification_service import SystemNotificationService
from .template_service import NotificationTemplateService
from .user_notification_service import NotificationService
from .user_settings_service import UserNotificationSettingsService

__all__ = [
    "NotificationService",
    "SystemNotificationService",
    "UserNotificationSettingsService",
    "NotificationTemplateService",
]
