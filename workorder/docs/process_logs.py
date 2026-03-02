"""
工序日志相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

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
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="工序日志分页列表",
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
                                        "id": 21,
                                        "log_type": "start",
                                        "log_type_display": "开始",
                                        "content": "开始工序",
                                        "created_at": "2026-03-02T09:10:00+08:00",
                                    }
                                ],
                            },
                            "timestamp": "2026-03-02T09:10:00+08:00",
                        },
                        response_only=True,
                    )
                ],
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
