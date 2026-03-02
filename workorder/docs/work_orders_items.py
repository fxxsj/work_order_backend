"""
施工单产品/物料相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

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
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="施工单物料分页列表",
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
                                        "id": 41,
                                        "material_name": "白卡纸",
                                        "material_code": "MAT-001",
                                        "purchase_status": "pending",
                                        "purchase_status_display": "待采购",
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
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="施工单产品分页列表",
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
                                        "product_name": "礼盒",
                                        "product_code": "PROD-001",
                                        "quantity": 1000,
                                        "unit": "件",
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
