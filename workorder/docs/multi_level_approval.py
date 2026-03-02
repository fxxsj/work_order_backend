"""
多级审核相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers

from workorder.schema import standard_error_response, standard_success_response
from workorder.serializers.multi_level_approval import (
    ApprovalEscalationSerializer,
    ApprovalRuleSerializer,
    ApprovalStepSerializer,
    ApprovalWorkflowSerializer,
)


approval_workflow_docs = extend_schema_view(
    list=extend_schema(
        tags=["审核"],
        summary="获取审核工作流列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ApprovalWorkflowListResponse"),
                description="工作流列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["审核"],
        summary="获取审核工作流详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ApprovalWorkflowDetailResponse", ApprovalWorkflowSerializer
                ),
                description="工作流详情",
            )
        },
    ),
)

approval_workflow_activate_docs = extend_schema(
    tags=["审核"],
    summary="激活工作流",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ApprovalWorkflowActivateResponse"),
            description="激活成功",
        )
    },
)

approval_workflow_deactivate_docs = extend_schema(
    tags=["审核"],
    summary="停用工作流",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ApprovalWorkflowDeactivateResponse"),
            description="停用成功",
        )
    },
)

approval_workflow_create_default_docs = extend_schema(
    tags=["审核"],
    summary="创建默认工作流",
    responses={
        201: OpenApiResponse(
            response=standard_success_response("ApprovalWorkflowCreateDefaultResponse"),
            description="创建成功",
        )
    },
)

approval_workflow_duplicate_docs = extend_schema(
    tags=["审核"],
    summary="复制工作流",
    request=inline_serializer(
        name="ApprovalWorkflowDuplicateRequest",
        fields={
            "source_id": serializers.IntegerField(),
            "new_name": serializers.CharField(),
        },
    ),
    responses={
        201: OpenApiResponse(
            response=standard_success_response("ApprovalWorkflowDuplicateResponse"),
            description="复制成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("ApprovalWorkflowDuplicateBadRequest"),
            description="请求无效",
        ),
    },
)


approval_step_docs = extend_schema_view(
    list=extend_schema(
        tags=["审核"],
        summary="获取审核步骤列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ApprovalStepListResponse"),
                description="步骤列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["审核"],
        summary="获取审核步骤详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ApprovalStepDetailResponse", ApprovalStepSerializer
                ),
                description="步骤详情",
            )
        },
    ),
)

approval_step_start_docs = extend_schema(
    tags=["审核"],
    summary="开始审核步骤",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ApprovalStepStartResponse"),
            description="开始成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("ApprovalStepStartBadRequest"),
            description="无法开始",
        ),
    },
)

approval_step_complete_docs = extend_schema(
    tags=["审核"],
    summary="完成审核步骤",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ApprovalStepCompleteResponse"),
            description="完成成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("ApprovalStepCompleteBadRequest"),
            description="无法完成",
        ),
    },
)

approval_step_escalate_docs = extend_schema(
    tags=["审核"],
    summary="上报审核步骤",
    responses={
        201: OpenApiResponse(
            response=standard_success_response("ApprovalStepEscalateResponse"),
            description="上报成功",
        )
    },
)


multi_level_submit_docs = extend_schema(
    tags=["审核"],
    summary="提交施工单审核",
    request=inline_serializer(
        name="MultiLevelSubmitRequest",
        fields={"order_id": serializers.IntegerField()},
    ),
    responses={
        200: OpenApiResponse(
            response=standard_success_response("MultiLevelSubmitResponse"),
            description="提交成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("MultiLevelSubmitBadRequest"),
            description="请求无效",
        ),
    },
)

multi_level_determine_docs = extend_schema(
    tags=["审核"],
    summary="确定审核流程",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("MultiLevelDetermineResponse"),
            description="确定成功",
        )
    },
)

multi_level_status_docs = extend_schema(
    tags=["审核"],
    summary="获取施工单审核状态",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("MultiLevelStatusResponse"),
            description="审核状态",
        )
    },
)

multi_level_my_tasks_docs = extend_schema(
    tags=["审核"],
    summary="获取我的审核任务",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("MultiLevelMyTasksResponse"),
            description="审核任务",
        )
    },
)


urgent_mark_docs = extend_schema(
    tags=["审核"],
    summary="标记紧急订单",
    request=inline_serializer(
        name="UrgentOrderRequest",
        fields={
            "order_id": serializers.IntegerField(),
            "reason": serializers.CharField(required=False, allow_blank=True),
        },
    ),
    responses={
        200: OpenApiResponse(
            response=standard_success_response("UrgentOrderMarkResponse"),
            description="标记成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("UrgentOrderMarkBadRequest"),
            description="请求无效",
        ),
    },
)

urgent_list_docs = extend_schema(
    tags=["审核"],
    summary="获取紧急订单列表",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("UrgentOrderListResponse"),
            description="紧急订单列表",
        )
    },
)

escalation_history_docs = extend_schema(
    tags=["审核"],
    summary="获取上报历史",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("EscalationHistoryResponse"),
            description="上报历史",
        )
    },
)


approval_report_stats_docs = extend_schema(
    tags=["审核"],
    summary="审核统计报告",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ApprovalReportStatsResponse"),
            description="统计报告",
        )
    },
)

approval_report_dashboard_docs = extend_schema(
    tags=["审核"],
    summary="审核仪表板",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ApprovalReportDashboardResponse"),
            description="仪表板",
        )
    },
)
