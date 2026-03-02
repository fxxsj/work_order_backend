"""
财务相关视图集的 OpenAPI 文档定义。
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
from workorder.serializers.finance import (
    CostCenterSerializer,
    CostItemSerializer,
    InvoiceSerializer,
    PaymentPlanSerializer,
    PaymentSerializer,
    ProductionCostSerializer,
    StatementSerializer,
)


cost_center_docs = extend_schema_view(
    list=extend_schema(
        tags=["财务"],
        summary="获取成本中心列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("CostCenterListResponse"),
                description="成本中心列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["财务"],
        summary="获取成本中心详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "CostCenterDetailResponse", CostCenterSerializer
                ),
                description="成本中心详情",
            )
        },
    ),
)


cost_item_docs = extend_schema_view(
    list=extend_schema(
        tags=["财务"],
        summary="获取成本项目列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("CostItemListResponse"),
                description="成本项目列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["财务"],
        summary="获取成本项目详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "CostItemDetailResponse", CostItemSerializer
                ),
                description="成本项目详情",
            )
        },
    ),
)


production_cost_docs = extend_schema_view(
    list=extend_schema(
        tags=["财务"],
        summary="获取生产成本列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProductionCostListResponse"),
                description="生产成本列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["财务"],
        summary="获取生产成本详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ProductionCostDetailResponse", ProductionCostSerializer
                ),
                description="生产成本详情",
            )
        },
    ),
)

production_cost_material_docs = extend_schema(
    tags=["财务"],
    summary="计算材料成本",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ProductionCostMaterialResponse"),
            description="计算成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("ProductionCostMaterialBadRequest"),
            description="计算失败",
        ),
    },
)

production_cost_total_docs = extend_schema(
    tags=["财务"],
    summary="计算总成本",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ProductionCostTotalResponse"),
            description="计算成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("ProductionCostTotalBadRequest"),
            description="计算失败",
        ),
    },
)

production_cost_stats_docs = extend_schema(
    tags=["财务"],
    summary="成本统计",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ProductionCostStatsResponse"),
            description="成本统计",
        )
    },
)


invoice_docs = extend_schema_view(
    list=extend_schema(
        tags=["财务"],
        summary="获取发票列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("InvoiceListResponse"),
                description="发票列表",
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="发票分页列表",
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
                                        "id": 7,
                                        "invoice_number": "FP202603020001",
                                        "invoice_type": "vat_normal",
                                        "status": "draft",
                                        "status_display": "待开具",
                                        "amount": "12000.00",
                                        "customer_name": "示例客户",
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
        tags=["财务"],
        summary="获取发票详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "InvoiceDetailResponse", InvoiceSerializer
                ),
                description="发票详情",
            )
        },
    ),
)

invoice_submit_docs = extend_schema(
    tags=["财务"],
    summary="提交发票",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("InvoiceSubmitResponse"),
            description="提交成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("InvoiceSubmitBadRequest"),
            description="状态不允许",
        ),
    },
)

invoice_approve_docs = extend_schema(
    tags=["财务"],
    summary="审核发票",
    request=inline_serializer(
        name="InvoiceApproveRequest",
        fields={
            "approved": serializers.BooleanField(required=False, default=True),
            "approval_comment": serializers.CharField(required=False, allow_blank=True),
        },
    ),
    examples=[
        OpenApiExample(
            name="示例请求",
            summary="审核通过",
            value={"approved": True, "approval_comment": "资料齐全"},
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            response=standard_success_response("InvoiceApproveResponse"),
            description="审核成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("InvoiceApproveBadRequest"),
            description="状态不允许",
        ),
    },
)

invoice_summary_docs = extend_schema(
    tags=["财务"],
    summary="发票汇总",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("InvoiceSummaryResponse"),
            description="发票汇总",
        )
    },
)


payment_docs = extend_schema_view(
    list=extend_schema(
        tags=["财务"],
        summary="获取收款记录列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("PaymentListResponse"),
                description="收款记录列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["财务"],
        summary="获取收款记录详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "PaymentDetailResponse", PaymentSerializer
                ),
                description="收款记录详情",
            )
        },
    ),
)

payment_summary_docs = extend_schema(
    tags=["财务"],
    summary="收款汇总",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PaymentSummaryResponse"),
            description="收款汇总",
        )
    },
)


payment_plan_docs = extend_schema_view(
    list=extend_schema(
        tags=["财务"],
        summary="获取收款计划列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("PaymentPlanListResponse"),
                description="收款计划列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["财务"],
        summary="获取收款计划详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "PaymentPlanDetailResponse", PaymentPlanSerializer
                ),
                description="收款计划详情",
            )
        },
    ),
)

payment_plan_update_docs = extend_schema(
    tags=["财务"],
    summary="更新收款计划状态",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PaymentPlanUpdateResponse"),
            description="更新成功",
        )
    },
)


statement_docs = extend_schema_view(
    list=extend_schema(
        tags=["财务"],
        summary="获取对账单列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("StatementListResponse"),
                description="对账单列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["财务"],
        summary="获取对账单详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "StatementDetailResponse", StatementSerializer
                ),
                description="对账单详情",
            )
        },
    ),
)

statement_confirm_docs = extend_schema(
    tags=["财务"],
    summary="确认对账单",
    request=inline_serializer(
        name="StatementConfirmRequest",
        fields={
            "confirmed": serializers.BooleanField(required=False, default=True),
            "confirm_notes": serializers.CharField(required=False, allow_blank=True),
        },
    ),
    examples=[
        OpenApiExample(
            name="示例请求",
            summary="确认对账单",
            value={"confirmed": True, "confirm_notes": "核对无误"},
            request_only=True,
        )
    ],
    responses={
        200: OpenApiResponse(
            response=standard_success_response("StatementConfirmResponse"),
            description="确认成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("StatementConfirmBadRequest"),
            description="状态不允许",
        ),
    },
)

statement_generate_docs = extend_schema(
    tags=["财务"],
    summary="生成对账单",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("StatementGenerateResponse"),
            description="生成成功",
        )
    },
)
