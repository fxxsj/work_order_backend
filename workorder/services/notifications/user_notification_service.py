"""
用户通知服务

提供当前用户通知的已读/删除/统计/票据等操作。
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Dict

from django.db.models import QuerySet
from django.utils import timezone

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
        from django.core.cache import cache

        ticket = secrets.token_urlsafe(32)
        cache.set(f"ws_ticket:{ticket}", user_id, timeout=60)
        return {"ticket": ticket, "expires_in": 60}
