"""
任务自定义操作相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers

from workorder.schema import standard_error_response, standard_success_response


task_assign_docs = extend_schema(
    tags=["任务"],
    summary="分配任务给操作员",
    request=inline_serializer(
        name="TaskAssignRequest",
        fields={
            "operator_id": serializers.IntegerField(),
            "notes": serializers.CharField(required=False, allow_blank=True),
        },
    ),
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskAssignResponse"),
            description="分配成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("TaskAssignBadRequest"),
            description="请求无效",
        ),
        403: OpenApiResponse(
            response=standard_error_response("TaskAssignForbidden"),
            description="权限不足",
        ),
        409: OpenApiResponse(
            response=standard_error_response("TaskAssignConflict"),
            description="任务冲突",
        ),
        500: OpenApiResponse(
            response=standard_error_response("TaskAssignServerError"),
            description="服务器错误",
        ),
    },
)


task_department_operators_docs = extend_schema(
    tags=["任务"],
    summary="获取部门操作员列表",
    parameters=[
        OpenApiParameter(
            name="department_id",
            type=OpenApiTypes.INT,
            required=True,
            description="部门ID",
        )
    ],
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskDepartmentOperatorsResponse"),
            description="操作员列表",
        ),
        400: OpenApiResponse(
            response=standard_error_response("TaskDepartmentOperatorsBadRequest"),
            description="请求无效",
        ),
        404: OpenApiResponse(
            response=standard_error_response("TaskDepartmentOperatorsNotFound"),
            description="部门不存在",
        ),
    },
)


task_claim_docs = extend_schema(
    tags=["任务"],
    summary="认领任务",
    request=inline_serializer(
        name="TaskClaimRequest",
        fields={"notes": serializers.CharField(required=False, allow_blank=True)},
    ),
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskClaimResponse"),
            description="认领成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("TaskClaimBadRequest"),
            description="请求无效",
        ),
        409: OpenApiResponse(
            response=standard_error_response("TaskClaimConflict"),
            description="任务冲突",
        ),
        500: OpenApiResponse(
            response=standard_error_response("TaskClaimServerError"),
            description="服务器错误",
        ),
    },
)


task_claimable_docs = extend_schema(
    tags=["任务"],
    summary="获取可认领任务列表",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskClaimableListResponse"),
            description="可认领任务列表",
        ),
        500: OpenApiResponse(
            response=standard_error_response("TaskClaimableServerError"),
            description="服务器错误",
        ),
    },
)


task_operator_center_docs = extend_schema(
    tags=["任务"],
    summary="操作员任务中心",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskOperatorCenterResponse"),
            description="任务中心数据",
        )
    },
)
