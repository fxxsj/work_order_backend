"""
任务批量操作相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers

from workorder.schema import standard_error_response, standard_success_response


batch_update_quantity_docs = extend_schema(
    tags=["任务"],
    summary="批量更新任务数量",
    request=inline_serializer(
        name="TaskBatchUpdateQuantityRequest",
        fields={
            "task_ids": serializers.ListField(child=serializers.IntegerField()),
            "quantity_increment": serializers.JSONField(),
            "quantity_defective": serializers.JSONField(required=False),
            "notes": serializers.CharField(required=False, allow_blank=True),
        },
    ),
    examples=[
        OpenApiExample(
            name="示例请求",
            summary="批量更新数量",
            value={
                "task_ids": [101, 102],
                "quantity_increment": {"101": 10, "102": 5},
                "quantity_defective": {"101": 1, "102": 0},
                "notes": "批量更新",
            },
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskBatchUpdateQuantityResponse"),
            description="更新成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("TaskBatchUpdateQuantityBadRequest"),
            description="请求无效",
        ),
        403: OpenApiResponse(
            response=standard_error_response("TaskBatchUpdateQuantityForbidden"),
            description="权限不足",
        ),
    },
)


batch_delete_docs = extend_schema(
    tags=["任务"],
    summary="批量删除任务",
    request=inline_serializer(
        name="TaskBatchDeleteRequest",
        fields={"task_ids": serializers.ListField(child=serializers.IntegerField())},
    ),
    examples=[
        OpenApiExample(
            name="示例请求",
            summary="批量删除任务",
            value={"task_ids": [101, 102]},
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskBatchDeleteResponse"),
            description="删除成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("TaskBatchDeleteBadRequest"),
            description="请求无效",
        ),
    },
)
