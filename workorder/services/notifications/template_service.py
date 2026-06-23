"""
通知模板服务

提供通知模板的查询、更新与预览能力。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from rest_framework import status

from workorder.services.service_errors import ServiceError

logger = logging.getLogger(__name__)


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
            raise ServiceError(
                "缺少 template_name", code=status.HTTP_400_BAD_REQUEST
            )

        NotificationTemplate.seed_defaults()
        template = NotificationTemplate.objects.filter(
            key=template_name
        ).first()
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
    def preview_template(
        template_name: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
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
