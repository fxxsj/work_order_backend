"""
任务批量操作相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
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
