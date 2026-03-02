"""
通知模块其他视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers

from workorder.schema import standard_error_response, standard_success_response


system_notification_docs = extend_schema_view(
    create_announcement=extend_schema(
        tags=["通知"],
        summary="创建系统公告",
        request=inline_serializer(
            name="SystemAnnouncementRequest",
            fields={
                "title": serializers.CharField(),
                "content": serializers.CharField(),
                "recipient_ids": serializers.ListField(
                    child=serializers.IntegerField(), required=False
                ),
                "only_staff": serializers.BooleanField(required=False, default=False),
                "expires_in_days": serializers.IntegerField(required=False),
            },
        ),
        examples=[
            OpenApiExample(
                name="示例请求",
                summary="创建公告",
                value={
                    "title": "系统维护通知",
                    "content": "今晚 22:00 进行维护",
                    "only_staff": True,
                    "expires_in_days": 2,
                },
                request_only=True,
            )
        ],
        responses={
            201: OpenApiResponse(
                response=standard_success_response("SystemAnnouncementResponse"),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("SystemAnnouncementBadRequest"),
                description="请求无效",
            ),
        },
    ),
    send_urgent_alert=extend_schema(
        tags=["通知"],
        summary="发送紧急警报",
        request=inline_serializer(
            name="SystemUrgentAlertRequest",
            fields={
                "title": serializers.CharField(),
                "content": serializers.CharField(),
                "recipient_ids": serializers.ListField(
                    child=serializers.IntegerField(), required=False
                ),
                "only_staff": serializers.BooleanField(required=False, default=False),
            },
        ),
        examples=[
            OpenApiExample(
                name="示例请求",
                summary="发送紧急警报",
                value={
                    "title": "紧急停机",
                    "content": "设备故障，请暂停生产",
                    "recipient_ids": [1, 2],
                },
                request_only=True,
            )
        ],
        responses={
            201: OpenApiResponse(
                response=standard_success_response("SystemUrgentAlertResponse"),
                description="发送成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("SystemUrgentAlertBadRequest"),
                description="请求无效",
            ),
        },
    ),
    notification_settings=extend_schema(
        tags=["通知"],
        summary="获取通知设置",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("SystemNotificationSettingsResponse"),
                description="通知设置",
            )
        },
    ),
    update_notification_settings=extend_schema(
        tags=["通知"],
        summary="更新通知设置",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("SystemNotificationSettingsUpdateResponse"),
                description="更新成功",
            )
        },
    ),
    system_status=extend_schema(
        tags=["通知"],
        summary="获取通知系统状态",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("SystemNotificationStatusResponse"),
                description="系统状态",
            ),
            500: OpenApiResponse(
                response=standard_error_response("SystemNotificationStatusError"),
                description="系统异常",
            ),
        },
    ),
)


user_notification_settings_docs = extend_schema_view(
    get_settings=extend_schema(
        tags=["通知"],
        summary="获取用户通知设置",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("UserNotificationSettingsResponse"),
                description="用户通知设置",
            )
        },
    ),
    update_settings=extend_schema(
        tags=["通知"],
        summary="更新用户通知设置",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("UserNotificationSettingsUpdateResponse"),
                description="更新成功",
            )
        },
    ),
    notification_preferences=extend_schema(
        tags=["通知"],
        summary="获取通知偏好设置",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("UserNotificationPreferencesResponse"),
                description="通知偏好",
            )
        },
    ),
)


notification_template_docs = extend_schema_view(
    get_templates=extend_schema(
        tags=["通知"],
        summary="获取通知模板",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("NotificationTemplateListResponse"),
                description="模板列表",
            )
        },
    ),
    preview_template=extend_schema(
        tags=["通知"],
        summary="预览通知模板",
        request=inline_serializer(
            name="NotificationTemplatePreviewRequest",
            fields={
                "template_name": serializers.CharField(),
                "variables": serializers.DictField(required=False),
            },
        ),
        responses={
            200: OpenApiResponse(
                response=standard_success_response("NotificationTemplatePreviewResponse"),
                description="预览结果",
            ),
            404: OpenApiResponse(
                response=standard_error_response("NotificationTemplateNotFoundResponse"),
                description="模板不存在",
            ),
        },
    ),
)
