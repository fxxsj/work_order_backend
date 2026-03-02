"""
销售订单相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers

from workorder.schema import standard_error_response, standard_success_response
from workorder.serializers.sales import (
    SalesOrderDetailSerializer,
    SalesOrderItemSerializer,
)


sales_order_docs = extend_schema_view(
    list=extend_schema(
        tags=["销售"],
        summary="获取销售订单列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("SalesOrderListResponse"),
                description="销售订单列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["销售"],
        summary="获取销售订单详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "SalesOrderDetailResponse", SalesOrderDetailSerializer
                ),
                description="销售订单详情",
            )
        },
    ),
    create=extend_schema(
        tags=["销售"],
        summary="创建销售订单",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "SalesOrderCreateResponse", SalesOrderDetailSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("SalesOrderCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
)

sales_order_submit_docs = extend_schema(
    tags=["销售"],
    summary="提交销售订单",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("SalesOrderSubmitResponse"),
            description="提交成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("SalesOrderSubmitBadRequest"),
            description="请求无效",
        ),
    },
)

sales_order_approve_docs = extend_schema(
    tags=["销售"],
    summary="审核销售订单",
    request=inline_serializer(
        name="SalesOrderApproveRequest",
        fields={
            "approval_comment": serializers.CharField(required=False, allow_blank=True)
        },
    ),
    responses={
        200: OpenApiResponse(
            response=standard_success_response("SalesOrderApproveResponse"),
            description="审核成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("SalesOrderApproveBadRequest"),
            description="请求无效",
        ),
    },
)

sales_order_reject_docs = extend_schema(
    tags=["销售"],
    summary="拒绝销售订单",
    request=inline_serializer(
        name="SalesOrderRejectRequest",
        fields={"reason": serializers.CharField()},
    ),
    responses={
        200: OpenApiResponse(
            response=standard_success_response("SalesOrderRejectResponse"),
            description="拒绝成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("SalesOrderRejectBadRequest"),
            description="请求无效",
        ),
    },
)

sales_order_start_docs = extend_schema(
    tags=["销售"],
    summary="开始生产",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("SalesOrderStartResponse"),
            description="开始成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("SalesOrderStartBadRequest"),
            description="请求无效",
        ),
    },
)

sales_order_complete_docs = extend_schema(
    tags=["销售"],
    summary="完成订单",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("SalesOrderCompleteResponse"),
            description="完成成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("SalesOrderCompleteBadRequest"),
            description="请求无效",
        ),
    },
)

sales_order_cancel_docs = extend_schema(
    tags=["销售"],
    summary="取消订单",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("SalesOrderCancelResponse"),
            description="取消成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("SalesOrderCancelBadRequest"),
            description="请求无效",
        ),
    },
)

sales_order_item_docs = extend_schema_view(
    list=extend_schema(
        tags=["销售"],
        summary="获取销售订单明细列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("SalesOrderItemListResponse"),
                description="订单明细列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["销售"],
        summary="获取销售订单明细详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "SalesOrderItemDetailResponse", SalesOrderItemSerializer
                ),
                description="订单明细详情",
            )
        },
    ),
)
