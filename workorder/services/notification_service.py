"""
通知业务服务

将 notification.py 视图集中的业务逻辑下沉到服务层：
- NotificationService：用户通知的已读/删除/统计/票据
- SystemNotificationService：系统公告/紧急警报/系统设置/状态
- UserNotificationSettingsService：用户级通知偏好设置
- NotificationTemplateService：通知模板管理

视图层只负责参数提取、调用服务和格式化响应。

注意：本文件现仅作为 `services.notifications` 子包的向后兼容 re-export shim，
新代码建议直接从 `workorder.services.notifications` 导入。
"""

from workorder.services.notifications import (
    NotificationService,
    NotificationTemplateService,
    SystemNotificationService,
    UserNotificationSettingsService,
)

__all__ = [
    "NotificationService",
    "SystemNotificationService",
    "UserNotificationSettingsService",
    "NotificationTemplateService",
]
