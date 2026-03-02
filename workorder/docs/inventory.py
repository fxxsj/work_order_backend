"""
库存相关视图集的 OpenAPI 文档定义。
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
from workorder.serializers.inventory import (
    DeliveryItemSerializer,
    DeliveryOrderSerializer,
    ProductStockAdjustSerializer,
    ProductStockSerializer,
    QualityInspectionSerializer,
    StockInSerializer,
    StockOutSerializer,
)


product_stock_docs = extend_schema_view(
    list=extend_schema(
        tags=["库存"],
        summary="获取成品库存列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProductStockListResponse"),
                description="库存列表",
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="库存分页列表",
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
                                        "id": 10,
                                        "product": 12,
                                        "product_name": "礼盒",
                                        "batch_no": "RK202603020001-21",
                                        "quantity": "1000.00",
                                        "reserved_quantity": "0.00",
                                        "status": "in_stock",
                                        "status_display": "在库",
                                        "location": "A01-01-01",
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
        tags=["库存"],
        summary="获取成品库存详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ProductStockDetailResponse", ProductStockSerializer
                ),
                description="库存详情",
            )
        },
    ),
    create=extend_schema(
        tags=["库存"],
        summary="创建库存记录",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "ProductStockCreateResponse", ProductStockSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("ProductStockCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
)


product_stock_low_docs = extend_schema(
    tags=["库存"],
    summary="获取低库存预警",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ProductStockLowResponse"),
            description="低库存列表",
        )
    },
)

product_stock_expired_docs = extend_schema(
    tags=["库存"],
    summary="获取已过期库存",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ProductStockExpiredResponse"),
            description="过期库存列表",
        )
    },
)

product_stock_expiring_docs = extend_schema(
    tags=["库存"],
    summary="获取即将过期库存",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ProductStockExpiringResponse"),
            description="即将过期库存列表",
        )
    },
)

product_stock_summary_docs = extend_schema(
    tags=["库存"],
    summary="库存汇总",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ProductStockSummaryResponse"),
            description="库存汇总",
        )
    },
)

product_stock_adjust_docs = extend_schema(
    tags=["库存"],
    summary="库存调整",
    request=ProductStockAdjustSerializer,
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ProductStockAdjustResponse"),
            description="调整成功",
            examples=[
                OpenApiExample(
                    name="示例响应",
                    summary="库存调整返回",
                    value={
                        "success": True,
                        "code": 200,
                        "message": "操作成功",
                        "data": {
                            "message": "库存调整成功",
                            "old_quantity": 1000.0,
                            "new_quantity": 980.0,
                            "data": {
                                "id": 10,
                                "batch_no": "RK202603020001-21",
                                "quantity": "980.00",
                                "status": "in_stock",
                            },
                        },
                        "timestamp": "2026-03-02T10:00:00+08:00",
                    },
                    response_only=True,
                )
            ],
        ),
        400: OpenApiResponse(
            response=standard_error_response("ProductStockAdjustBadRequest"),
            description="请求无效",
        ),
    },
)


stock_in_docs = extend_schema_view(
    list=extend_schema(
        tags=["库存"],
        summary="获取入库单列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("StockInListResponse"),
                description="入库单列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["库存"],
        summary="获取入库单详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "StockInDetailResponse", StockInSerializer
                ),
                description="入库单详情",
            )
        },
    ),
)

stock_in_submit_docs = extend_schema(
    tags=["库存"],
    summary="提交入库单",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("StockInSubmitResponse"),
            description="提交成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("StockInSubmitBadRequest"),
            description="状态不允许",
        ),
    },
)

stock_in_approve_docs = extend_schema(
    tags=["库存"],
    summary="审核入库单",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("StockInApproveResponse"),
            description="审核成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("StockInApproveBadRequest"),
            description="状态不允许",
        ),
    },
)


stock_out_docs = extend_schema_view(
    list=extend_schema(
        tags=["库存"],
        summary="获取出库单列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("StockOutListResponse"),
                description="出库单列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["库存"],
        summary="获取出库单详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "StockOutDetailResponse", StockOutSerializer
                ),
                description="出库单详情",
            )
        },
    ),
)

stock_out_approve_docs = extend_schema(
    tags=["库存"],
    summary="审核出库单",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("StockOutApproveResponse"),
            description="审核成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("StockOutApproveBadRequest"),
            description="状态不允许",
        ),
    },
)


delivery_item_docs = extend_schema_view(
    list=extend_schema(
        tags=["库存"],
        summary="获取发货明细列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("DeliveryItemListResponse"),
                description="发货明细列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["库存"],
        summary="获取发货明细详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "DeliveryItemDetailResponse", DeliveryItemSerializer
                ),
                description="发货明细详情",
            )
        },
    ),
)


delivery_order_docs = extend_schema_view(
    list=extend_schema(
        tags=["库存"],
        summary="获取发货单列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("DeliveryOrderListResponse"),
                description="发货单列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["库存"],
        summary="获取发货单详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "DeliveryOrderDetailResponse", DeliveryOrderSerializer
                ),
                description="发货单详情",
            )
        },
    ),
)

delivery_ship_docs = extend_schema(
    tags=["库存"],
    summary="发货",
    request=inline_serializer(
        name="DeliveryShipRequest",
        fields={
            "logistics_company": serializers.CharField(required=False, allow_blank=True),
            "tracking_number": serializers.CharField(required=False, allow_blank=True),
        },
    ),
    examples=[
        OpenApiExample(
            name="示例请求",
            summary="发货请求体",
            value={
                "logistics_company": "顺丰",
                "tracking_number": "SF123456789",
            },
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            response=standard_success_response("DeliveryShipResponse"),
            description="发货成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("DeliveryShipBadRequest"),
            description="状态不允许",
        ),
    },
)

delivery_receive_docs = extend_schema(
    tags=["库存"],
    summary="签收",
    request=inline_serializer(
        name="DeliveryReceiveRequest",
        fields={
            "received_notes": serializers.CharField(required=False, allow_blank=True),
        },
    ),
    examples=[
        OpenApiExample(
            name="示例请求",
            summary="签收请求体",
            value={"received_notes": "外包装完好"},
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            response=standard_success_response("DeliveryReceiveResponse"),
            description="签收成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("DeliveryReceiveBadRequest"),
            description="状态不允许",
        ),
    },
)

delivery_reject_docs = extend_schema(
    tags=["库存"],
    summary="拒收",
    request=inline_serializer(
        name="DeliveryRejectRequest",
        fields={
            "reject_reason": serializers.CharField(required=True),
        },
    ),
    examples=[
        OpenApiExample(
            name="示例请求",
            summary="拒收原因",
            value={"reject_reason": "包装破损"},
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            response=standard_success_response("DeliveryRejectResponse"),
            description="拒收成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("DeliveryRejectBadRequest"),
            description="状态不允许",
        ),
    },
)

delivery_summary_docs = extend_schema(
    tags=["库存"],
    summary="发货汇总",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("DeliverySummaryResponse"),
            description="发货汇总",
        )
    },
)


quality_inspection_docs = extend_schema_view(
    list=extend_schema(
        tags=["库存"],
        summary="获取质检列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("QualityInspectionListResponse"),
                description="质检列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["库存"],
        summary="获取质检详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "QualityInspectionDetailResponse", QualityInspectionSerializer
                ),
                description="质检详情",
            )
        },
    ),
)

quality_complete_docs = extend_schema(
    tags=["库存"],
    summary="完成质检",
    request=inline_serializer(
        name="QualityInspectionCompleteRequest",
        fields={
            "result": serializers.CharField(),
            "passed_quantity": serializers.IntegerField(required=False, default=0),
            "failed_quantity": serializers.IntegerField(required=False, default=0),
        },
    ),
    examples=[
        OpenApiExample(
            name="示例请求",
            summary="提交质检结果",
            value={"result": "passed", "passed_quantity": 980, "failed_quantity": 20},
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            response=standard_success_response("QualityInspectionCompleteResponse"),
            description="完成成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("QualityInspectionCompleteBadRequest"),
            description="请求无效",
        ),
    },
)

quality_summary_docs = extend_schema(
    tags=["库存"],
    summary="质检汇总",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("QualityInspectionSummaryResponse"),
            description="质检汇总",
        )
    },
)
