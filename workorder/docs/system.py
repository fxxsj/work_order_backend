"""
系统管理相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from workorder.schema import standard_error_response, standard_success_response
from workorder.serializers.system import NotificationSerializer, TaskAssignmentRuleSerializer


notification_docs = extend_schema_view(
    list=extend_schema(
        tags=["通知"],
        summary="获取通知列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("SystemNotificationListResponse"),
                description="通知列表",
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="通知分页列表",
                        value={
                            "success": True,
                            "code": 200,
                            "message": "操作成功",
                            "data": {
                                "count": 1,
                                "next": None,
                                "previous": None,
                                "results": [
                                    {
                                        "id": 11,
                                        "title": "任务提醒",
                                        "notification_type": "task_assigned",
                                        "is_read": False,
                                        "created_at": "2026-03-02T09:00:00+08:00",
                                    }
                                ],
                            },
                            "timestamp": "2026-03-02T09:00:00+08:00",
                        },
                        response_only=True,
                    )
                ],
            )
        },
    ),
    retrieve=extend_schema(
        tags=["通知"],
        summary="获取通知详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "SystemNotificationDetailResponse", NotificationSerializer
                ),
                description="通知详情",
            )
        },
    ),
)

notification_mark_read_docs = extend_schema(
    tags=["通知"],
    summary="标记通知为已读",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("SystemNotificationMarkReadResponse"),
            description="标记成功",
        )
    },
)

notification_mark_all_docs = extend_schema(
    tags=["通知"],
    summary="标记全部通知为已读",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("SystemNotificationMarkAllResponse"),
            description="标记成功",
        )
    },
)

notification_unread_docs = extend_schema(
    tags=["通知"],
    summary="获取未读通知数量",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("SystemNotificationUnreadResponse"),
            description="未读数量",
        )
    },
)


task_assignment_rule_docs = extend_schema_view(
    list=extend_schema(
        tags=["系统"],
        summary="获取任务分派规则列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("TaskAssignmentRuleListResponse"),
                description="分派规则列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["系统"],
        summary="获取任务分派规则详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "TaskAssignmentRuleDetailResponse", TaskAssignmentRuleSerializer
                ),
                description="分派规则详情",
            )
        },
    ),
)

task_assignment_preview_docs = extend_schema(
    tags=["系统"],
    summary="生成分派预览",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskAssignmentPreviewResponse"),
            description="分派预览",
        )
    },
)

task_assignment_global_state_docs = extend_schema(
    tags=["系统"],
    summary="获取全局自动分派状态",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskAssignmentGlobalStateResponse"),
            description="全局状态",
        )
    },
)

task_assignment_set_state_docs = extend_schema(
    tags=["系统"],
    summary="设置全局自动分派状态",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskAssignmentSetStateResponse"),
            description="设置成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("TaskAssignmentSetStateBadRequest"),
            description="请求无效",
        ),
    },
)
