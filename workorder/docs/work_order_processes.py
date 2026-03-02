"""
施工单工序相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view

from workorder.schema import standard_error_response, standard_success_response
from workorder.serializers.core import WorkOrderProcessSerializer


work_order_process_docs = extend_schema_view(
    list=extend_schema(
        tags=["施工单"],
        summary="获取工序列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("WorkOrderProcessListResponse"),
                description="工序列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["施工单"],
        summary="获取工序详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "WorkOrderProcessDetailResponse", WorkOrderProcessSerializer
                ),
                description="工序详情",
            )
        },
    ),
)

process_start_docs = extend_schema(
    tags=["施工单"],
    summary="开始工序",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("WorkOrderProcessStartResponse"),
            description="开始成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("WorkOrderProcessStartBadRequest"),
            description="无法开始",
        ),
    },
)

process_complete_docs = extend_schema(
    tags=["施工单"],
    summary="完成工序",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("WorkOrderProcessCompleteResponse"),
            description="完成成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("WorkOrderProcessCompleteBadRequest"),
            description="无法完成",
        ),
    },
)

process_bulk_create_docs = extend_schema(
    tags=["施工单"],
    summary="为施工单批量创建工序",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("WorkOrderProcessBulkCreateResponse"),
            description="创建成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("WorkOrderProcessBulkCreateBadRequest"),
            description="请求无效",
        ),
    },
)

process_reassign_docs = extend_schema(
    tags=["施工单"],
    summary="批量重新分派工序任务",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("WorkOrderProcessReassignResponse"),
            description="分派成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("WorkOrderProcessReassignBadRequest"),
            description="请求无效",
        ),
    },
)
