"""
物料相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view

from workorder.schema import standard_error_response, standard_success_response
from workorder.serializers.materials import (
    InspectionConfirmSerializer,
    MaterialSerializer,
    MaterialSupplierSerializer,
    PurchaseOrderDetailSerializer,
    PurchaseOrderItemSerializer,
    PurchaseOrderListSerializer,
    PurchaseReceiveRecordCreateSerializer,
    PurchaseReceiveRecordSerializer,
    ReturnProcessSerializer,
    SupplierSerializer,
)


material_docs = extend_schema_view(
    list=extend_schema(
        tags=["物料"],
        summary="获取物料列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("MaterialListResponse"),
                description="物料列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["物料"],
        summary="获取物料详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "MaterialDetailResponse", MaterialSerializer
                ),
                description="物料详情",
            )
        },
    ),
    create=extend_schema(
        tags=["物料"],
        summary="创建物料",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "MaterialCreateResponse", MaterialSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("MaterialCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
    destroy=extend_schema(
        tags=["物料"],
        summary="删除物料",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("MaterialDeleteResponse"),
                description="删除成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("MaterialDeleteBadRequest"),
                description="删除失败",
            ),
        },
    ),
)


supplier_docs = extend_schema_view(
    list=extend_schema(
        tags=["物料"],
        summary="获取供应商列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("SupplierListResponse"),
                description="供应商列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["物料"],
        summary="获取供应商详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "SupplierDetailResponse", SupplierSerializer
                ),
                description="供应商详情",
            )
        },
    ),
    create=extend_schema(
        tags=["物料"],
        summary="创建供应商",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "SupplierCreateResponse", SupplierSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("SupplierCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
)


material_supplier_docs = extend_schema_view(
    list=extend_schema(
        tags=["物料"],
        summary="获取物料供应商关联列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("MaterialSupplierListResponse"),
                description="物料供应商列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["物料"],
        summary="获取物料供应商关联详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "MaterialSupplierDetailResponse", MaterialSupplierSerializer
                ),
                description="物料供应商详情",
            )
        },
    ),
    create=extend_schema(
        tags=["物料"],
        summary="创建物料供应商关联",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "MaterialSupplierCreateResponse", MaterialSupplierSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("MaterialSupplierCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
)


purchase_order_docs = extend_schema_view(
    list=extend_schema(
        tags=["物料"],
        summary="获取采购单列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("PurchaseOrderListResponse"),
                description="采购单列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["物料"],
        summary="获取采购单详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "PurchaseOrderDetailResponse", PurchaseOrderDetailSerializer
                ),
                description="采购单详情",
            )
        },
    ),
    create=extend_schema(
        tags=["物料"],
        summary="创建采购单",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "PurchaseOrderCreateResponse", PurchaseOrderDetailSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("PurchaseOrderCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
)


purchase_order_item_docs = extend_schema_view(
    list=extend_schema(
        tags=["物料"],
        summary="获取采购单明细列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("PurchaseOrderItemListResponse"),
                description="采购单明细列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["物料"],
        summary="获取采购单明细详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "PurchaseOrderItemDetailResponse", PurchaseOrderItemSerializer
                ),
                description="采购单明细详情",
            )
        },
    ),
)


purchase_receive_record_docs = extend_schema_view(
    list=extend_schema(
        tags=["物料"],
        summary="获取收货记录列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("PurchaseReceiveRecordListResponse"),
                description="收货记录列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["物料"],
        summary="获取收货记录详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "PurchaseReceiveRecordDetailResponse",
                    PurchaseReceiveRecordSerializer,
                ),
                description="收货记录详情",
            )
        },
    ),
)


purchase_order_submit_docs = extend_schema(
    tags=["物料"],
    summary="提交采购单",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PurchaseOrderSubmitResponse"),
            description="提交成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("PurchaseOrderSubmitBadRequest"),
            description="状态不允许",
        ),
    },
)

purchase_order_approve_docs = extend_schema(
    tags=["物料"],
    summary="批准采购单",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PurchaseOrderApproveResponse"),
            description="批准成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("PurchaseOrderApproveBadRequest"),
            description="状态不允许",
        ),
    },
)

purchase_order_reject_docs = extend_schema(
    tags=["物料"],
    summary="拒绝采购单",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PurchaseOrderRejectResponse"),
            description="拒绝成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("PurchaseOrderRejectBadRequest"),
            description="状态不允许",
        ),
    },
)

purchase_order_place_docs = extend_schema(
    tags=["物料"],
    summary="采购单下单",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PurchaseOrderPlaceResponse"),
            description="下单成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("PurchaseOrderPlaceBadRequest"),
            description="状态不允许",
        ),
    },
)

purchase_order_receive_docs = extend_schema(
    tags=["物料"],
    summary="采购单收货",
    request=PurchaseReceiveRecordCreateSerializer,
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PurchaseOrderReceiveResponse"),
            description="收货成功",
        ),
        207: OpenApiResponse(
            response=standard_success_response("PurchaseOrderReceivePartialResponse"),
            description="部分收货成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("PurchaseOrderReceiveBadRequest"),
            description="请求无效",
        ),
    },
)

purchase_order_cancel_docs = extend_schema(
    tags=["物料"],
    summary="取消采购单",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PurchaseOrderCancelResponse"),
            description="取消成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("PurchaseOrderCancelBadRequest"),
            description="状态不允许",
        ),
    },
)

purchase_order_receive_records_docs = extend_schema(
    tags=["物料"],
    summary="获取采购单收货记录",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PurchaseOrderReceiveRecordsResponse"),
            description="收货记录列表",
        )
    },
)

purchase_order_pending_inspections_docs = extend_schema(
    tags=["物料"],
    summary="获取待质检收货记录",
    responses={
        200: OpenApiResponse(
            response=standard_success_response(
                "PurchaseOrderPendingInspectionResponse"
            ),
            description="待质检收货记录",
        )
    },
)

materials_low_stock_docs = extend_schema(
    tags=["物料"],
    summary="获取库存预警物料",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("MaterialLowStockResponse"),
            description="库存预警物料",
        )
    },
)

receive_confirm_inspection_docs = extend_schema(
    tags=["物料"],
    summary="确认质检结果",
    request=InspectionConfirmSerializer,
    responses={
        200: OpenApiResponse(
            response=standard_success_response(
                "PurchaseReceiveConfirmInspectionResponse"
            ),
            description="确认成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response(
                "PurchaseReceiveConfirmInspectionBadRequest"
            ),
            description="请求无效",
        ),
    },
)

receive_stock_in_docs = extend_schema(
    tags=["物料"],
    summary="合格物料入库",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PurchaseReceiveStockInResponse"),
            description="入库成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("PurchaseReceiveStockInBadRequest"),
            description="状态不允许",
        ),
    },
)

receive_return_docs = extend_schema(
    tags=["物料"],
    summary="处理退货",
    request=ReturnProcessSerializer,
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PurchaseReceiveReturnResponse"),
            description="退货成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("PurchaseReceiveReturnBadRequest"),
            description="请求无效",
        ),
    },
)

receive_pending_list_docs = extend_schema(
    tags=["物料"],
    summary="获取待质检收货记录（全局）",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PurchaseReceivePendingListResponse"),
            description="待质检列表",
        )
    },
)

receive_pending_stock_docs = extend_schema(
    tags=["物料"],
    summary="获取待入库收货记录",
    responses={
        200: OpenApiResponse(
            response=standard_success_response(
                "PurchaseReceivePendingStockInResponse"
            ),
            description="待入库列表",
        )
    },
)

receive_pending_return_docs = extend_schema(
    tags=["物料"],
    summary="获取待退货收货记录",
    responses={
        200: OpenApiResponse(
            response=standard_success_response(
                "PurchaseReceivePendingReturnResponse"
            ),
            description="待退货列表",
        )
    },
)
