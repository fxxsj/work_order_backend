"""
多级审核相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
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
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="工作流分页列表",
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
                                        "id": 1,
                                        "name": "默认审核流程",
                                        "is_active": True,
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
    examples=[
        OpenApiExample(
            name="示例请求",
            summary="复制工作流",
            value={"source_id": 1, "new_name": "默认流程-副本"},
            request_only=True,
        )
    ],
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
    examples=[
        OpenApiExample(
            name="示例请求",
            summary="提交审核",
            value={"order_id": 1},
            request_only=True,
        )
    ],
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

smart_assign_task_docs = extend_schema(
    tags=["审核"],
    summary="智能分配任务",
    request=inline_serializer(
        name="ApprovalSmartAssignTaskRequest",
        fields={"task_id": serializers.IntegerField()},
    ),
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ApprovalSmartAssignTaskResponse"),
            description="分配成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("ApprovalSmartAssignTaskBadRequest"),
            description="请求无效",
        ),
        403: OpenApiResponse(
            response=standard_error_response("ApprovalSmartAssignTaskForbidden"),
            description="权限不足",
        ),
        404: OpenApiResponse(
            response=standard_error_response("ApprovalSmartAssignTaskNotFound"),
            description="任务不存在",
        ),
    },
)

smart_assign_workorder_docs = extend_schema(
    tags=["审核"],
    summary="智能分配施工单任务",
    request=inline_serializer(
        name="ApprovalSmartAssignWorkOrderRequest",
        fields={"workorder_id": serializers.IntegerField()},
    ),
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ApprovalSmartAssignWorkOrderResponse"),
            description="分配成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("ApprovalSmartAssignWorkOrderBadRequest"),
            description="请求无效",
        ),
        403: OpenApiResponse(
            response=standard_error_response("ApprovalSmartAssignWorkOrderForbidden"),
            description="权限不足",
        ),
        404: OpenApiResponse(
            response=standard_error_response("ApprovalSmartAssignWorkOrderNotFound"),
            description="施工单不存在",
        ),
    },
)

team_skill_analysis_docs = extend_schema(
    tags=["审核"],
    summary="团队技能分析",
    parameters=[
        OpenApiParameter(
            name="department_id",
            type=OpenApiTypes.INT,
            required=False,
            description="部门ID",
        )
    ],
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ApprovalTeamSkillAnalysisResponse"),
            description="分析结果",
        ),
        403: OpenApiResponse(
            response=standard_error_response("ApprovalTeamSkillAnalysisForbidden"),
            description="权限不足",
        ),
    },
)

user_performance_summary_docs = extend_schema(
    tags=["审核"],
    summary="用户绩效统计",
    parameters=[
        OpenApiParameter(
            name="user_id",
            type=OpenApiTypes.INT,
            required=True,
            description="用户ID",
        )
    ],
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ApprovalUserPerformanceResponse"),
            description="统计结果",
        ),
        400: OpenApiResponse(
            response=standard_error_response("ApprovalUserPerformanceBadRequest"),
            description="请求无效",
        ),
        403: OpenApiResponse(
            response=standard_error_response("ApprovalUserPerformanceForbidden"),
            description="权限不足",
        ),
        404: OpenApiResponse(
            response=standard_error_response("ApprovalUserPerformanceNotFound"),
            description="用户不存在",
        ),
    },
)

update_skill_profile_docs = extend_schema(
    tags=["审核"],
    summary="更新用户技能档案",
    responses={
        501: OpenApiResponse(
            response=standard_error_response("ApprovalSkillProfileNotImplemented"),
            description="功能不可用",
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
    examples=[
        OpenApiExample(
            name="示例请求",
            summary="标记紧急",
            value={"order_id": 1, "reason": "客户要求提前交付"},
            request_only=True,
        )
    ],
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
