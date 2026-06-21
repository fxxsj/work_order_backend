"""
实时通知视图和序列化器

提供通知管理、WebSocket连接、通知设置等功能
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
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

from ..models.system import Notification
from ..services.notifications import (
    NotificationService,
    NotificationTemplateService,
    SystemNotificationService,
    UserNotificationSettingsService,
)
from ..services.service_errors import ServiceError
from ._decorators import handle_service_error


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
            status.HTTP_200_OK: OpenApiResponse(
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

        page = self.paginate_queryset(notifications)
        if page is not None:
            data = [NotificationSerializer.serialize_notification(n) for n in page]
            paginated = self.get_paginated_response(data)
            return APIResponse.success(data=paginated.data)

        data = [NotificationSerializer.serialize_notification(n) for n in notifications]
        return APIResponse.success(data=data)

    @action(detail=True, methods=["post"])
    @extend_schema(
        tags=["通知"],
        summary="标记通知为已读",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=standard_success_response("NotificationMarkReadActionResponse"),
                description="标记成功",
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                response=standard_error_response("NotificationMarkReadNotFound"),
                description="通知不存在",
            ),
        },
    )
    def mark_read(self, request, pk=None):
        """标记通知为已读"""
        try:
            notification = self.get_queryset().get(id=pk)
            NotificationService.mark_read(notification)
            return APIResponse.success(
                data={
                    "notification": NotificationSerializer.serialize_notification(notification),
                },
                message="通知已标记为已读",
            )
        except Notification.DoesNotExist:
            return APIResponse.error("通知不存在", code=status.HTTP_404_NOT_FOUND)
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

    @action(detail=False, methods=["post"])
    @extend_schema(
        tags=["通知"],
        summary="标记所有通知为已读",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=standard_success_response("NotificationMarkAllReadResponse"),
                description="批量标记成功",
            )
        },
    )
    @handle_service_error
    def mark_all_read(self, request):
        """标记所有通知为已读"""
        count = NotificationService.mark_all_read(self.get_queryset())
        return APIResponse.success(
            data={"count": count},
            message=f"已标记 {count} 条通知为已读",
        )

    @action(detail=True, methods=["delete"])
    @extend_schema(
        tags=["通知"],
        summary="删除通知",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=standard_success_response("NotificationDeleteResponse"),
                description="删除成功",
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                response=standard_error_response("NotificationDeleteNotFoundResponse"),
                description="通知不存在",
            ),
        },
    )
    def delete(self, request, pk=None):
        """删除通知"""
        try:
            notification = self.get_queryset().get(id=pk)
            NotificationService.delete(notification)
            return APIResponse.success(message="通知已删除")
        except Notification.DoesNotExist:
            return APIResponse.error("通知不存在", code=status.HTTP_404_NOT_FOUND)
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

    @action(detail=False, methods=["delete"])
    @extend_schema(
        tags=["通知"],
        summary="删除所有已读通知",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=standard_success_response("NotificationDeleteAllReadResponse"),
                description="删除成功",
            )
        },
    )
    @handle_service_error
    def delete_all_read(self, request):
        """删除所有已读通知"""
        count = NotificationService.delete_all_read(self.get_queryset())
        return APIResponse.success(data={"count": count}, message=f"已删除 {count} 条已读通知")

    @action(detail=False, methods=["get"])
    @extend_schema(
        tags=["通知"],
        summary="获取未读通知数量",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=standard_success_response("NotificationUnreadCountResponse"),
                description="未读数量",
            )
        },
    )
    @handle_service_error
    def unread_count(self, request):
        """获取未读通知数量"""
        count = NotificationService.unread_count(self.get_queryset())
        return APIResponse.success(data={"unread_count": count})

    @action(detail=False, methods=["get"])
    @extend_schema(
        tags=["通知"],
        summary="获取通知统计",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=standard_success_response("NotificationStatisticsResponse"),
                description="通知统计",
            )
        },
    )
    @handle_service_error
    def statistics(self, request):
        """获取通知统计"""
        queryset = self.filter_queryset(self.get_queryset())
        data = NotificationService.statistics(queryset)
        return APIResponse.success(data=data)

    @action(detail=False, methods=["post"])
    @extend_schema(
        tags=["通知"],
        summary="获取 WebSocket 连接票据",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=standard_success_response("NotificationWsTicketResponse"),
                description="连接票据",
            )
        },
    )
    @handle_service_error
    def ws_ticket(self, request):
        """获取 WebSocket 连接票据（短期有效，一次性使用）"""
        data = NotificationService.ws_ticket(request.user.id)
        return APIResponse.success(data=data)


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

    @handle_service_error
    def list(self, request):
        queryset = self.filter_queryset(self._get_announcement_queryset())
        ordering = request.query_params.get("ordering") or "-created_at"
        rows = SystemNotificationService.list_announcements(
            queryset, ordering, self.ordering_fields
        )

        page = self.paginate_queryset(rows)
        if page is not None:
            data = [SystemNotificationAdminSerializer.serialize_row(row) for row in page]
            paginated = self.get_paginated_response(data)
            return APIResponse.success(data=paginated.data)

        data = [SystemNotificationAdminSerializer.serialize_row(row) for row in rows]
        return APIResponse.success(data=data)

    @action(detail=False, methods=["post"])
    @handle_service_error
    def create_announcement(self, request):
        """创建系统公告"""
        result = SystemNotificationService.create_announcement(
            title=(request.data.get("title") or "").strip(),
            content=(request.data.get("content") or "").strip(),
            recipient_ids=request.data.get("recipient_ids"),
            only_staff=bool(request.data.get("only_staff", False)),
            expires_in_days=request.data.get("expires_in_days"),
            priority=request.data.get("priority") or "normal",
        )
        return APIResponse.success(
            data=result,
            message="系统公告已创建",
            code=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"])
    @handle_service_error
    def send_urgent_alert(self, request):
        """发送紧急警报"""
        result = SystemNotificationService.send_urgent_alert(
            title=(request.data.get("title") or "").strip(),
            content=(request.data.get("content") or "").strip(),
            recipient_ids=request.data.get("recipient_ids"),
            only_staff=bool(request.data.get("only_staff", False)),
        )
        return APIResponse.success(
            data=result,
            message="紧急警报已发送",
            code=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["delete"])
    @handle_service_error
    def revoke(self, request, pk=None):
        """撤回系统公告批次。"""
        count = SystemNotificationService.revoke(pk)
        return APIResponse.success(
            data={"count": count},
            message="系统通知已撤回",
        )

    @action(detail=False, methods=["get"])
    @handle_service_error
    def notification_settings(self, request):
        """获取通知设置"""
        return APIResponse.success(data=SystemNotificationService.get_settings())

    @action(detail=False, methods=["post"])
    @handle_service_error
    def update_notification_settings(self, request):
        """更新通知设置"""
        data = SystemNotificationService.update_settings(request.data)
        return APIResponse.success(data=data, message="通知设置已更新")

    @action(detail=False, methods=["get"])
    def system_status(self, request):
        """获取通知系统状态"""
        try:
            return APIResponse.success(data=SystemNotificationService.system_status())
        except ServiceError as exc:
            return APIResponse.error(
                exc.message,
                code=exc.code,
                errors=exc.data,
            )


@user_notification_settings_docs
class UserNotificationSettingsViewSet(viewsets.GenericViewSet):
    """用户通知设置视图集"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmptySerializer

    @action(detail=False, methods=["get"])
    @handle_service_error
    def get_settings(self, request):
        """获取用户通知设置"""
        data = UserNotificationSettingsService.get_settings(request.user)
        return APIResponse.success(data=data)

    @action(detail=False, methods=["post"])
    @handle_service_error
    def update_settings(self, request):
        """更新用户通知设置"""
        data = UserNotificationSettingsService.update_settings(
            request.user, request.data
        )
        return APIResponse.success(data=data, message="通知设置已更新")

    @action(detail=False, methods=["get"])
    @handle_service_error
    def notification_preferences(self, request):
        """获取通知偏好设置"""
        return APIResponse.success(
            data=UserNotificationSettingsService.get_notification_preferences()
        )


@notification_template_docs
class NotificationTemplateViewSet(viewsets.GenericViewSet):
    """通知模板视图集"""

    permission_classes = [IsSystemNotificationAdmin]
    serializer_class = EmptySerializer

    @action(detail=False, methods=["get"])
    @handle_service_error
    def get_templates(self, request):
        """获取通知模板"""
        return APIResponse.success(data=NotificationTemplateService.get_templates())

    @action(detail=False, methods=["post"])
    @handle_service_error
    def update_template(self, request):
        """更新通知模板"""
        result = NotificationTemplateService.update_template(
            template_name=(request.data.get("template_name") or "").strip(),
            title=request.data.get("title"),
            message=request.data.get("message"),
            variables=request.data.get("variables"),
            is_active=request.data.get("is_active"),
        )
        return APIResponse.success(data=result, message="模板已更新")

    @action(detail=False, methods=["post"])
    @handle_service_error
    def preview_template(self, request):
        """预览通知模板"""
        result = NotificationTemplateService.preview_template(
            template_name=request.data.get("template_name"),
            variables=request.data.get("variables", {}),
        )
        return APIResponse.success(data=result)
