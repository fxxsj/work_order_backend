"""
工序日志相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view

from workorder.schema import standard_success_response
from workorder.serializers.core import ProcessLogSerializer


process_log_docs = extend_schema_view(
    list=extend_schema(
        tags=["工序"],
        summary="获取工序日志列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProcessLogListResponse"),
                description="工序日志列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["工序"],
        summary="获取工序日志详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ProcessLogDetailResponse", ProcessLogSerializer
                ),
                description="工序日志详情",
            )
        },
    ),
)
