"""
施工单相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers

from workorder.schema import standard_error_response, standard_success_response
from workorder.serializers.core import (
    WorkOrderDetailSerializer,
    WorkOrderProcessSerializer,
    WorkOrderMaterialSerializer,
)


work_order_docs = extend_schema_view(
    list=extend_schema(
        tags=["施工单"],
        summary="获取施工单列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("WorkOrderListResponse"),
                description="施工单列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["施工单"],
        summary="获取施工单详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "WorkOrderDetailResponse", WorkOrderDetailSerializer
                ),
                description="施工单详情",
            )
        },
    ),
    create=extend_schema(
        tags=["施工单"],
        summary="创建施工单",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "WorkOrderCreateResponse", WorkOrderDetailSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("WorkOrderCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
)


work_order_add_process_docs = extend_schema(
    tags=["施工单"],
    summary="添加工序",
    request=inline_serializer(
        name="WorkOrderAddProcessRequest",
        fields={
            "process_id": serializers.IntegerField(),
            "sequence": serializers.IntegerField(required=False, default=0),
        },
    ),
    responses={
        201: OpenApiResponse(
            response=standard_success_response(
                "WorkOrderAddProcessResponse", WorkOrderProcessSerializer
            ),
            description="添加成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("WorkOrderAddProcessBadRequest"),
            description="请求无效",
        ),
    },
)

work_order_add_material_docs = extend_schema(
    tags=["施工单"],
    summary="添加物料",
    request=inline_serializer(
        name="WorkOrderAddMaterialRequest",
        fields={
            "material_id": serializers.IntegerField(),
            "notes": serializers.CharField(required=False, allow_blank=True),
        },
    ),
    responses={
        201: OpenApiResponse(
            response=standard_success_response(
                "WorkOrderAddMaterialResponse", WorkOrderMaterialSerializer
            ),
            description="添加成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("WorkOrderAddMaterialBadRequest"),
            description="请求无效",
        ),
    },
)

work_order_update_status_docs = extend_schema(
    tags=["施工单"],
    summary="更新施工单状态",
    request=inline_serializer(
        name="WorkOrderUpdateStatusRequest",
        fields={"status": serializers.CharField()},
    ),
    responses={
        200: OpenApiResponse(
            response=standard_success_response(
                "WorkOrderUpdateStatusResponse", WorkOrderDetailSerializer
            ),
            description="更新成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response(
                "WorkOrderUpdateStatusBadRequest"
            ),
            description="请求无效",
        ),
    },
)

work_order_statistics_docs = extend_schema(
    tags=["施工单"],
    summary="施工单统计",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("WorkOrderStatisticsResponse"),
            description="统计数据",
        )
    },
)

work_order_summary_docs = extend_schema(
    tags=["施工单"],
    summary="施工单汇总",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("WorkOrderSummaryResponse"),
            description="汇总数据",
        )
    },
)

work_order_export_docs = extend_schema(
    tags=["施工单"],
    summary="导出施工单",
    responses={
        200: OpenApiResponse(description="导出文件"),
        400: OpenApiResponse(
            response=standard_error_response("WorkOrderExportBadRequest"),
            description="导出失败",
        ),
    },
)

work_order_sync_preview_docs = extend_schema(
    tags=["施工单"],
    summary="同步任务预览",
    request=inline_serializer(
        name="WorkOrderSyncPreviewRequest",
        fields={
            "process_ids": serializers.ListField(
                child=serializers.IntegerField()
            )
        },
    ),
    responses={
        200: OpenApiResponse(
            response=standard_success_response("WorkOrderSyncPreviewResponse"),
            description="预览成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("WorkOrderSyncPreviewBadRequest"),
            description="请求无效",
        ),
    },
)

work_order_sync_execute_docs = extend_schema(
    tags=["施工单"],
    summary="执行任务同步",
    request=inline_serializer(
        name="WorkOrderSyncExecuteRequest",
        fields={
            "process_ids": serializers.ListField(
                child=serializers.IntegerField()
            ),
            "confirmed": serializers.BooleanField(),
        },
    ),
    responses={
        200: OpenApiResponse(
            response=standard_success_response("WorkOrderSyncExecuteResponse"),
            description="同步完成",
        ),
        400: OpenApiResponse(
            response=standard_error_response("WorkOrderSyncExecuteBadRequest"),
            description="请求无效",
        ),
    },
)

work_order_sync_check_docs = extend_schema(
    tags=["施工单"],
    summary="检查是否需要同步任务",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("WorkOrderSyncCheckResponse"),
            description="检查结果",
        )
    },
)
