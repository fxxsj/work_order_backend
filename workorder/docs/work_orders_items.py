"""
施工单产品/物料相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view

from workorder.schema import standard_success_response
from workorder.serializers.core import WorkOrderMaterialSerializer, WorkOrderProductSerializer


work_order_material_docs = extend_schema_view(
    list=extend_schema(
        tags=["施工单"],
        summary="获取施工单物料列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("WorkOrderMaterialListResponse"),
                description="施工单物料列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["施工单"],
        summary="获取施工单物料详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "WorkOrderMaterialDetailResponse", WorkOrderMaterialSerializer
                ),
                description="施工单物料详情",
            )
        },
    ),
)


work_order_product_docs = extend_schema_view(
    list=extend_schema(
        tags=["施工单"],
        summary="获取施工单产品列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("WorkOrderProductListResponse"),
                description="施工单产品列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["施工单"],
        summary="获取施工单产品详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "WorkOrderProductDetailResponse", WorkOrderProductSerializer
                ),
                description="施工单产品详情",
            )
        },
    ),
)
