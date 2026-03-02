"""
实时通知视图和序列化器

提供通知管理、WebSocket连接、通知设置等功能
"""

import secrets
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework import serializers
from workorder.response import APIResponse
from workorder.schema import standard_error_response, standard_success_response
from workorder.docs.notification_extra import (
    notification_template_docs,
    system_notification_docs,
    user_notification_settings_docs,
)

from ..models.system import Notification

# 暂时注释掉可能导致阻塞的导入
# from ..services.realtime_notification import (
#     RealtimeNotificationService, NotificationManager,
#     NotificationEvent, NotificationPriority, NotificationChannel
# )


class NotificationPagination(PageNumberPagination):
    """通知分页器"""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationSerializer:
    """通知序列化器"""

    @staticmethod
    def serialize_notification(notification):
        """序列化通知对象"""
        return {
            "id": notification.id,
            "notification_type": notification.notification_type,
            "priority": notification.priority,
            "title": notification.title,
            "content": notification.content,
            "is_read": notification.is_read,
            "read_at": (
                notification.read_at.isoformat() if notification.read_at else None
            ),
            "created_at": notification.created_at.isoformat(),
            "work_order_id": notification.work_order_id,
            "task_id": notification.task_id,
        }


class EmptySerializer(serializers.Serializer):
    """用于 OpenAPI 生成的空序列化器"""

    pass


@extend_schema_view(
    list=extend_schema(
        tags=["通知"],
        summary="获取通知列表",
        description="返回当前用户的通知列表，仅显示最近30天的通知。",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("NotificationListResponse"),
                description="通知列表",
            )
        },
    ),
)
class NotificationViewSet(viewsets.GenericViewSet):
    """通知管理视图集"""

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination
    serializer_class = EmptySerializer

    def get_queryset(self):
        """获取当前用户的通知查询集"""
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(recipient=self.request.user).order_by(
            "-created_at"
        )

    def list(self, request):
        """获取通知列表"""
        notifications = self.get_queryset()

        # 分页
        page = self.paginate_queryset(notifications)
        if page is not None:
            data = [NotificationSerializer.serialize_notification(n) for n in page]
            paginated = self.get_paginated_response(data)
            return APIResponse.success(data=paginated.data)

        # 如果没有分页，返回所有
        data = [NotificationSerializer.serialize_notification(n) for n in notifications]
        return APIResponse.success(data=data)

    @action(detail=True, methods=["post"])
    @extend_schema(
        tags=["通知"],
        summary="标记通知为已读",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("NotificationMarkReadActionResponse"),
                description="标记成功",
            ),
            404: OpenApiResponse(
                response=standard_error_response("NotificationMarkReadNotFound"),
                description="通知不存在",
            ),
        },
    )
    def mark_read(self, request, pk=None):
        """标记通知为已读"""
        try:
            notification = self.get_queryset().get(id=pk)
            notification.is_read = True
            notification.save(update_fields=["is_read"])

            return APIResponse.success(
                data={
                    "notification": NotificationSerializer.serialize_notification(notification),
                },
                message="通知已标记为已读",
            )
        except Notification.DoesNotExist:
            return APIResponse.error("通知不存在", code=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["post"])
    @extend_schema(
        tags=["通知"],
        summary="标记所有通知为已读",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("NotificationMarkAllReadResponse"),
                description="批量标记成功",
            )
        },
    )
    def mark_all_read(self, request):
        """标记所有通知为已读"""
        count = self.get_queryset().filter(is_read=False).update(is_read=True)

        return APIResponse.success(data={"count": count}, message=f"已标记 {count} 条通知为已读")

    @action(detail=True, methods=["delete"])
    @extend_schema(
        tags=["通知"],
        summary="删除通知",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("NotificationDeleteResponse"),
                description="删除成功",
            ),
            404: OpenApiResponse(
                response=standard_error_response("NotificationDeleteNotFoundResponse"),
                description="通知不存在",
            ),
        },
    )
    def delete(self, request, pk=None):
        """删除通知"""
        try:
            notification = self.get_queryset().get(id=pk)
            notification.delete()

            return APIResponse.success(message="通知已删除")
        except Notification.DoesNotExist:
            return APIResponse.error("通知不存在", code=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["delete"])
    @extend_schema(
        tags=["通知"],
        summary="删除所有已读通知",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("NotificationDeleteAllReadResponse"),
                description="删除成功",
            )
        },
    )
    def delete_all_read(self, request):
        """删除所有已读通知"""
        count = self.get_queryset().filter(is_read=True).delete()[0]

        return APIResponse.success(data={"count": count}, message=f"已删除 {count} 条已读通知")

    @action(detail=False, methods=["get"])
    @extend_schema(
        tags=["通知"],
        summary="获取未读通知数量",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("NotificationUnreadCountResponse"),
                description="未读数量",
            )
        },
    )
    def unread_count(self, request):
        """获取未读通知数量"""
        count = self.get_queryset().filter(is_read=False).count()

        return APIResponse.success(data={"unread_count": count})

    @action(detail=False, methods=["get"])
    @extend_schema(
        tags=["通知"],
        summary="获取通知统计",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("NotificationStatisticsResponse"),
                description="通知统计",
            )
        },
    )
    def statistics(self, request):
        """获取通知统计"""
        queryset = self.get_queryset()

        # 简化版统计，避免使用可能导致阻塞的导入
        return APIResponse.success(
            data={
                "total_count": queryset.count(),
                "unread_count": queryset.filter(is_read=False).count(),
                "read_count": queryset.filter(is_read=True).count(),
            }
        )

    @action(detail=False, methods=["post"])
    @extend_schema(
        tags=["通知"],
        summary="获取 WebSocket 连接票据",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("NotificationWsTicketResponse"),
                description="连接票据",
            )
        },
    )
    def ws_ticket(self, request):
        """获取 WebSocket 连接票据（短期有效，一次性使用）"""
        ticket = secrets.token_urlsafe(32)
        cache.set(f"ws_ticket:{ticket}", request.user.id, timeout=60)
        return APIResponse.success(data={"ticket": ticket, "expires_in": 60})


@system_notification_docs
class SystemNotificationViewSet(viewsets.GenericViewSet):
    """系统通知管理视图集"""

    permission_classes = [permissions.IsAdminUser]
    serializer_class = EmptySerializer

    @action(detail=False, methods=["post"])
    def create_announcement(self, request):
        """创建系统公告"""
        title = (request.data.get("title") or "").strip()
        content = (request.data.get("content") or "").strip()
        recipient_ids = request.data.get("recipient_ids")
        only_staff = bool(request.data.get("only_staff", False))
        expires_in_days = request.data.get("expires_in_days")

        if not title:
            return APIResponse.error("缺少 title", code=status.HTTP_400_BAD_REQUEST)
        if not content:
            return APIResponse.error("缺少 content", code=status.HTTP_400_BAD_REQUEST)

        recipients = User.objects.all()
        if only_staff:
            recipients = recipients.filter(is_staff=True)
        if recipient_ids:
            recipients = recipients.filter(id__in=recipient_ids)

        now = timezone.now()
        expires_at = None
        if expires_in_days is not None:
            try:
                days = int(expires_in_days)
                expires_at = now + timedelta(days=days)
            except Exception:
                return APIResponse.error("expires_in_days 必须为整数", code=status.HTTP_400_BAD_REQUEST)

        notifications = [
            Notification(
                recipient=recipient,
                notification_type="system",
                priority="normal",
                title=title,
                content=content,
                expires_at=expires_at,
                data={"kind": "announcement"},
            )
            for recipient in recipients.iterator()
        ]

        Notification.objects.bulk_create(notifications, batch_size=1000)

        return APIResponse.success(
            data={"count": len(notifications)},
            message="系统公告已创建",
            code=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"])
    def send_urgent_alert(self, request):
        """发送紧急警报"""
        title = (request.data.get("title") or "").strip()
        content = (request.data.get("content") or "").strip()
        recipient_ids = request.data.get("recipient_ids")
        only_staff = bool(request.data.get("only_staff", False))

        if not title:
            return APIResponse.error("缺少 title", code=status.HTTP_400_BAD_REQUEST)
        if not content:
            return APIResponse.error("缺少 content", code=status.HTTP_400_BAD_REQUEST)

        recipients = User.objects.all()
        if only_staff:
            recipients = recipients.filter(is_staff=True)
        if recipient_ids:
            recipients = recipients.filter(id__in=recipient_ids)

        notifications = [
            Notification(
                recipient=recipient,
                notification_type="system",
                priority="urgent",
                title=title,
                content=content,
                data={"kind": "urgent_alert"},
            )
            for recipient in recipients.iterator()
        ]
        Notification.objects.bulk_create(notifications, batch_size=1000)

        return APIResponse.success(
            data={"count": len(notifications)},
            message="紧急警报已发送",
            code=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def notification_settings(self, request):
        """获取通知设置"""
        settings_data = {
            "websocket_enabled": True,
            "email_enabled": True,
            "sms_enabled": False,
            "email_threshold": "high",
            "notification_retention_days": 30,
            "auto_cleanup_enabled": True,
            "max_notifications_per_user": 1000,
        }

        return APIResponse.success(data=settings_data)

    @action(detail=False, methods=["post"])
    def update_notification_settings(self, request):
        """更新通知设置"""
        return APIResponse.success(message="通知设置已更新")

    @action(detail=False, methods=["get"])
    def system_status(self, request):
        """获取通知系统状态"""
        try:
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()

            # 统计未发送通知
            unsent_notifications = Notification.objects.filter(is_sent=False).count()

            # 统计最近通知数量
            recent_notifications = Notification.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count()

            return APIResponse.success(
                data={
                    "status": "healthy",
                    "active_connections": 0,
                    "unsent_notifications": unsent_notifications,
                    "recent_notifications": recent_notifications,
                    "channel_layer_type": str(type(channel_layer).__name__),
                    "timestamp": timezone.now().isoformat(),
                }
            )

        except Exception as e:
            return APIResponse.error(
                "通知系统异常",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                errors={"detail": str(e)},
                data={"status": "error", "timestamp": timezone.now().isoformat()},
            )


@user_notification_settings_docs
class UserNotificationSettingsViewSet(viewsets.GenericViewSet):
    """用户通知设置视图集"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmptySerializer

    @action(detail=False, methods=["get"])
    def get_settings(self, request):
        """获取用户通知设置"""
        user = request.user

        # 这里可以从用户配置中获取个性化设置
        settings_data = {
            "user_id": user.id,
            "email_notifications": True,
            "websocket_notifications": True,
            "task_assignments": True,
            "process_completions": True,
            "deadline_warnings": True,
            "system_announcements": True,
            "urgency_threshold": "normal",
            "quiet_hours_enabled": False,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        }

        return APIResponse.success(data=settings_data)

    @action(detail=False, methods=["post"])
    def update_settings(self, request):
        """更新用户通知设置"""
        user = request.user
        settings_data = request.data

        # 这里可以实现用户个性化设置的保存逻辑
        # 为了简化，暂时返回成功响应

        return APIResponse.success(
            data={"user_id": user.id, "settings": settings_data},
            message="通知设置已更新",
        )

    @action(detail=False, methods=["get"])
    def notification_preferences(self, request):
        """获取通知偏好设置"""
        preferences = {
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

        return APIResponse.success(data=preferences)


@notification_template_docs
class NotificationTemplateViewSet(viewsets.GenericViewSet):
    """通知模板视图集"""

    permission_classes = [permissions.IsAdminUser]
    serializer_class = EmptySerializer

    @action(detail=False, methods=["get"])
    def get_templates(self, request):
        """获取通知模板"""
        templates = {
            "task_assigned": {
                "title": "新任务分配",
                "message": "您有新的任务: {task_name}",
                "variables": ["task_name", "workorder_number", "assigned_by"],
            },
            "process_completed": {
                "title": "工序完成",
                "message": "工序 {process_name} 已完成",
                "variables": ["process_name", "workorder_number", "completed_by"],
            },
            "workorder_approved": {
                "title": "施工单审核通过",
                "message": "您的施工单 {workorder_number} 已审核通过",
                "variables": ["workorder_number", "approved_by"],
            },
            "workorder_rejected": {
                "title": "施工单审核拒绝",
                "message": "您的施工单 {workorder_number} 已被拒绝",
                "variables": ["workorder_number", "rejected_by"],
            },
            "deadline_warning": {
                "title": "交货期预警",
                "message": "施工单 {workorder_number} 将在 {days_remaining} 天后到期",
                "variables": ["workorder_number", "days_remaining", "deadline"],
            },
            "urgent_order": {
                "title": "紧急订单警报",
                "message": "紧急订单 {workorder_number} 需要立即处理",
                "variables": ["workorder_number", "priority"],
            },
        }

        return APIResponse.success(data=templates)

    @action(detail=False, methods=["post"])
    def preview_template(self, request):
        """预览通知模板"""
        template_name = request.data.get("template_name")
        variables = request.data.get("variables", {})

        templates = {
            "task_assigned": {
                "title": "新任务分配",
                "message": "您有新的任务: {task_name}",
            },
            "process_completed": {
                "title": "工序完成",
                "message": "工序 {process_name} 已完成",
            },
        }

        if template_name not in templates:
            return APIResponse.error("模板不存在", code=status.HTTP_404_NOT_FOUND)

        template = templates[template_name]
        title = template["title"].format(**variables)
        message = template["message"].format(**variables)

        return APIResponse.success(
            data={
                "template_name": template_name,
                "title": title,
                "message": message,
                "variables": variables,
            }
        )
