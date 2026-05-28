"""
实时通知视图和序列化器

提供通知管理、WebSocket连接、通知设置等功能
"""

import secrets
import re
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, mixins, permissions, status, viewsets
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

from ..models.system import (
    Notification,
    NotificationTemplate,
    SystemNotificationSettings,
    UserProfile,
    default_user_notification_preferences,
)

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
            "notification_type_display": notification.get_notification_type_display(),
            "priority": notification.priority,
            "priority_display": notification.get_priority_display(),
            "title": notification.title,
            "content": notification.content,
            "is_read": notification.is_read,
            "read_at": (
                notification.read_at.isoformat() if notification.read_at else None
            ),
            "created_at": notification.created_at.isoformat(),
            "expires_at": (
                notification.expires_at.isoformat() if notification.expires_at else None
            ),
            "work_order_id": notification.work_order_id,
            "work_order_process_id": notification.work_order_process_id,
            "task_id": notification.task_id,
            "purchase_order_id": notification.purchase_order_id,
            "data": notification.data or {},
        }


class SystemNotificationAdminSerializer:
    """系统通知管理列表序列化器。"""

    @staticmethod
    def serialize_row(row):
        data = row.get("data") or {}
        return {
            "id": data.get("batch_id") or row["max_id"],
            "batch_id": data.get("batch_id") or row["max_id"],
            "notification_type": row["notification_type"],
            "notification_type_display": "系统通知",
            "priority": row["priority"],
            "priority_display": dict(Notification.PRIORITY_CHOICES).get(
                row["priority"], row["priority"]
            ),
            "title": row["title"],
            "content": row["content"],
            "recipient_count": row["recipient_count"],
            "read_count": row["read_count"] or 0,
            "unread_count": row["recipient_count"] - (row["read_count"] or 0),
            "is_sent": bool(row["sent_count"] or 0),
            "created_at": row["created_at"].isoformat(),
            "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
            "data": data,
        }


class EmptySerializer(serializers.Serializer):
    """用于 OpenAPI 生成的空序列化器"""

    pass


class IsSystemNotificationAdmin(permissions.BasePermission):
    """系统通知管理权限。"""

    permission_codes = (
        "workorder.view_systemnotificationsettings",
        "workorder.change_systemnotificationsettings",
        "workorder.view_notificationtemplate",
        "workorder.add_notificationtemplate",
        "workorder.change_notificationtemplate",
        "workorder.delete_notificationtemplate",
    )

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True
        return any(user.has_perm(code) for code in self.permission_codes)


class NotificationFilterSet(django_filters.FilterSet):
    """用户通知列表筛选。"""

    is_read = django_filters.BooleanFilter(field_name="is_read")
    notification_type = django_filters.CharFilter(field_name="notification_type")
    priority = django_filters.CharFilter(field_name="priority")
    work_order = django_filters.NumberFilter(field_name="work_order_id")
    work_order_id = django_filters.NumberFilter(field_name="work_order_id")
    task = django_filters.NumberFilter(field_name="task_id")
    task_id = django_filters.NumberFilter(field_name="task_id")
    purchase_order = django_filters.NumberFilter(field_name="purchase_order_id")
    purchase_order_id = django_filters.NumberFilter(field_name="purchase_order_id")
    start_date = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__gte",
    )
    end_date = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__lte",
    )
    created_at_after = django_filters.IsoDateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
    )
    created_at_before = django_filters.IsoDateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
    )

    class Meta:
        model = Notification
        fields = [
            "is_read",
            "notification_type",
            "priority",
            "work_order",
            "work_order_id",
            "task",
            "task_id",
            "purchase_order",
            "purchase_order_id",
            "start_date",
            "end_date",
            "created_at_after",
            "created_at_before",
        ]


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
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = NotificationFilterSet
    search_fields = [
        "title",
        "content",
        "notification_type",
        "priority",
        "work_order__order_number",
        "task__work_content",
        "purchase_order__order_number",
    ]
    ordering_fields = [
        "created_at",
        "read_at",
        "notification_type",
        "priority",
        "is_read",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        """获取当前用户的通知查询集"""
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        Notification.apply_retention_policy([self.request.user.id])
        return Notification.objects.filter(recipient=self.request.user)

    def list(self, request):
        """获取通知列表"""
        notifications = self.filter_queryset(self.get_queryset())

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
            notification.mark_as_read()

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
        count = self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
        )

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
        queryset = self.filter_queryset(self.get_queryset())

        # 简化版统计，避免使用可能导致阻塞的导入
        return APIResponse.success(
            data={
                "total_count": queryset.count(),
                "unread_count": queryset.filter(is_read=False).count(),
                "read_count": queryset.filter(is_read=True).count(),
                "urgent_count": queryset.filter(priority="urgent").count(),
                "high_count": queryset.filter(priority="high").count(),
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
class SystemNotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """系统通知管理视图集"""

    permission_classes = [IsSystemNotificationAdmin]
    pagination_class = NotificationPagination
    serializer_class = EmptySerializer
    filter_backends = []
    search_fields = ["title", "content"]
    ordering_fields = [
        "created_at",
        "priority",
        "title",
        "recipient_count",
        "read_count",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        """系统通知管理列表按发布批次聚合。"""
        queryset = Notification.objects.filter(notification_type="system")

        priority = self.request.query_params.get("priority")
        if priority:
            queryset = queryset.filter(priority=priority)

        kind = self.request.query_params.get("kind")
        if kind:
            queryset = queryset.filter(data__kind=kind)

        start_date = self.request.query_params.get("start_date")
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)

        end_date = self.request.query_params.get("end_date")
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )

        return queryset

    def _get_announcement_queryset(self):
        return self.get_queryset().filter(data__kind__in=["announcement", "urgent_alert"])

    def _get_batch_queryset(self, batch_id):
        return Notification.objects.filter(
            notification_type="system",
            data__batch_id=str(batch_id),
        )

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        ordering = self.request.query_params.get("ordering") or "-created_at"
        allowed = {field.lstrip("-") for field in self.ordering_fields}
        if ordering.lstrip("-") not in allowed:
            ordering = "-created_at"
        return queryset.order_by(ordering)

    def list(self, request):
        queryset = self.filter_queryset(self._get_announcement_queryset())
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
        ordering = request.query_params.get("ordering") or "-created_at"
        reverse = ordering.startswith("-")
        sort_key = ordering.lstrip("-")
        if sort_key in {field.lstrip("-") for field in self.ordering_fields}:
            rows.sort(key=lambda row: row.get(sort_key) or 0, reverse=reverse)

        page = self.paginate_queryset(rows)
        if page is not None:
            data = [SystemNotificationAdminSerializer.serialize_row(row) for row in page]
            paginated = self.get_paginated_response(data)
            return APIResponse.success(data=paginated.data)

        data = [SystemNotificationAdminSerializer.serialize_row(row) for row in rows]
        return APIResponse.success(data=data)

    def _serialize_settings(self, settings):
        return {
            "websocket_enabled": settings.websocket_enabled,
            "email_enabled": settings.email_enabled,
            "sms_enabled": settings.sms_enabled,
            "email_threshold": settings.email_threshold,
            "notification_retention_days": settings.notification_retention_days,
            "auto_cleanup_enabled": settings.auto_cleanup_enabled,
            "max_notifications_per_user": settings.max_notifications_per_user,
        }

    @action(detail=False, methods=["post"])
    def create_announcement(self, request):
        """创建系统公告"""
        title = (request.data.get("title") or "").strip()
        content = (request.data.get("content") or "").strip()
        recipient_ids = request.data.get("recipient_ids")
        only_staff = bool(request.data.get("only_staff", False))
        expires_in_days = request.data.get("expires_in_days")
        priority = request.data.get("priority") or "normal"

        if not title:
            return APIResponse.error("缺少 title", code=status.HTTP_400_BAD_REQUEST)
        if not content:
            return APIResponse.error("缺少 content", code=status.HTTP_400_BAD_REQUEST)
        if priority not in dict(Notification.PRIORITY_CHOICES):
            return APIResponse.error("priority 不合法", code=status.HTTP_400_BAD_REQUEST)

        recipients = User.objects.all()
        if only_staff:
            recipients = recipients.filter(is_staff=True)
        if recipient_ids:
            recipients = recipients.filter(id__in=recipient_ids)
        recipient_ids_for_policy = list(recipients.values_list("id", flat=True))

        now = timezone.now()
        batch_id = secrets.token_urlsafe(12)
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

        return APIResponse.success(
            data={"count": len(notifications), "batch_id": batch_id},
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

        return APIResponse.success(
            data={"count": len(notifications), "batch_id": batch_id},
            message="紧急警报已发送",
            code=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["delete"])
    def revoke(self, request, pk=None):
        """撤回系统公告批次。"""
        queryset = self._get_batch_queryset(pk)
        deleted_count = queryset.count()
        if deleted_count == 0:
            return APIResponse.error("通知不存在", code=status.HTTP_404_NOT_FOUND)
        queryset.delete()
        return APIResponse.success(
            data={"count": deleted_count},
            message="系统通知已撤回",
        )

    @action(detail=False, methods=["get"])
    def notification_settings(self, request):
        """获取通知设置"""
        settings = SystemNotificationSettings.get_solo()
        return APIResponse.success(data=self._serialize_settings(settings))

    @action(detail=False, methods=["post"])
    def update_notification_settings(self, request):
        """更新通知设置"""
        settings = SystemNotificationSettings.get_solo()
        payload = request.data

        threshold = payload.get("email_threshold", settings.email_threshold)
        valid_thresholds = {
            choice[0] for choice in SystemNotificationSettings.EMAIL_THRESHOLD_CHOICES
        }
        if threshold not in valid_thresholds:
            return APIResponse.error(
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
        except (TypeError, ValueError):
            return APIResponse.error(
                "通知设置中的数值字段必须为整数",
                code=status.HTTP_400_BAD_REQUEST,
            )

        if retention_days <= 0 or max_notifications <= 0:
            return APIResponse.error(
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

        return APIResponse.success(
            data=self._serialize_settings(settings),
            message="通知设置已更新",
        )

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

    def _get_profile(self, user):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not profile.notification_preferences:
            profile.notification_preferences = default_user_notification_preferences()
            profile.save(update_fields=["notification_preferences", "updated_at"])
        return profile

    def _serialize_preferences(self, profile):
        prefs = default_user_notification_preferences()
        prefs.update(profile.notification_preferences or {})
        prefs["user_id"] = profile.user_id
        return prefs

    def _validate_time_text(self, value, field_name):
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
            return APIResponse.error(
                f"{field_name} 必须为 HH:MM 格式",
                code=status.HTTP_400_BAD_REQUEST,
            )
        return None

    @action(detail=False, methods=["get"])
    def get_settings(self, request):
        """获取用户通知设置"""
        profile = self._get_profile(request.user)
        return APIResponse.success(data=self._serialize_preferences(profile))

    @action(detail=False, methods=["post"])
    def update_settings(self, request):
        """更新用户通知设置"""
        profile = self._get_profile(request.user)
        payload = request.data
        current = default_user_notification_preferences()
        current.update(profile.notification_preferences or {})

        urgency_threshold = (
            payload.get("urgency_threshold", current["urgency_threshold"]) or "normal"
        ).strip()
        if urgency_threshold not in {"low", "normal", "high", "urgent"}:
            return APIResponse.error(
                "urgency_threshold 不合法",
                code=status.HTTP_400_BAD_REQUEST,
            )

        quiet_start = (
            payload.get("quiet_hours_start", current["quiet_hours_start"]) or "22:00"
        ).strip()
        quiet_end = (
            payload.get("quiet_hours_end", current["quiet_hours_end"]) or "08:00"
        ).strip()
        invalid = self._validate_time_text(quiet_start, "quiet_hours_start")
        if invalid is not None:
            return invalid
        invalid = self._validate_time_text(quiet_end, "quiet_hours_end")
        if invalid is not None:
            return invalid

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

        return APIResponse.success(
            data=self._serialize_preferences(profile),
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

    permission_classes = [IsSystemNotificationAdmin]
    serializer_class = EmptySerializer

    def _serialize_templates(self):
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

    @action(detail=False, methods=["get"])
    def get_templates(self, request):
        """获取通知模板"""
        return APIResponse.success(data=self._serialize_templates())

    @action(detail=False, methods=["post"])
    def update_template(self, request):
        """更新通知模板"""
        template_name = (request.data.get("template_name") or "").strip()
        if not template_name:
            return APIResponse.error("缺少 template_name", code=status.HTTP_400_BAD_REQUEST)

        NotificationTemplate.seed_defaults()
        template = NotificationTemplate.objects.filter(key=template_name).first()
        if template is None:
            return APIResponse.error("模板不存在", code=status.HTTP_404_NOT_FOUND)

        title = request.data.get("title")
        message = request.data.get("message")
        variables = request.data.get("variables")
        is_active = request.data.get("is_active")

        if title is not None:
            template.title = str(title).strip()
        if message is not None:
            template.message = str(message).strip()
        if variables is not None:
            if not isinstance(variables, list):
                return APIResponse.error("variables 必须为数组", code=status.HTTP_400_BAD_REQUEST)
            template.variables = [str(item) for item in variables]
        if is_active is not None:
            template.is_active = bool(is_active)

        if not template.title or not template.message:
            return APIResponse.error("标题和内容不能为空", code=status.HTTP_400_BAD_REQUEST)

        template.save()
        return APIResponse.success(
            data={
                "template_name": template.key,
                "title": template.title,
                "message": template.message,
                "variables": template.variables,
                "is_active": template.is_active,
            },
            message="模板已更新",
        )

    @action(detail=False, methods=["post"])
    def preview_template(self, request):
        """预览通知模板"""
        template_name = request.data.get("template_name")
        variables = request.data.get("variables", {})
        if not isinstance(variables, dict):
            return APIResponse.error("variables 必须为对象", code=status.HTTP_400_BAD_REQUEST)

        rendered = NotificationTemplate.render(template_name, variables)
        if not rendered:
            return APIResponse.error("模板不存在", code=status.HTTP_404_NOT_FOUND)

        return APIResponse.success(
            data={
                "template_name": template_name,
                "title": rendered["title"],
                "message": rendered["message"],
                "variables": variables,
            }
        )
