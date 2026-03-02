"""
任务统计相关视图集的 OpenAPI 文档定义。
"""

from rest_framework import serializers
from drf_spectacular.utils import OpenApiResponse, extend_schema

from workorder.schema import standard_error_response, standard_success_response


class TaskExportRequestSerializer(serializers.Serializer):
    """任务导出请求体"""

    filters = serializers.DictField(required=False)
    task_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )
    columns = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )


task_export_docs = extend_schema(
    tags=["任务"],
    summary="导出任务列表",
    responses={
        200: OpenApiResponse(description="导出文件"),
        403: OpenApiResponse(
            response=standard_error_response("TaskExportForbidden"),
            description="权限不足",
        ),
    },
)

task_export_post_docs = extend_schema(
    tags=["任务"],
    summary="导出任务列表（自定义列）",
    description="通过筛选条件或任务ID导出任务列表，并支持指定导出列。",
    request=TaskExportRequestSerializer,
    responses={
        200: OpenApiResponse(description="导出文件"),
        400: OpenApiResponse(
            response=standard_error_response("TaskExportBadRequest"),
            description="请求参数无效",
        ),
        403: OpenApiResponse(
            response=standard_error_response("TaskExportForbidden"),
            description="权限不足",
        ),
    },
)

task_assignment_history_docs = extend_schema(
    tags=["任务"],
    summary="分派历史查询",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskAssignmentHistoryResponse"),
            description="分派历史",
        )
    },
)

task_collaboration_stats_docs = extend_schema(
    tags=["任务"],
    summary="协作统计",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskCollaborationStatsResponse"),
            description="协作统计",
        )
    },
)

task_department_workload_docs = extend_schema(
    tags=["任务"],
    summary="部门工作负载统计",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskDepartmentWorkloadResponse"),
            description="部门工作负载",
        ),
        400: OpenApiResponse(
            response=standard_error_response("TaskDepartmentWorkloadBadRequest"),
            description="请求无效",
        ),
        403: OpenApiResponse(
            response=standard_error_response("TaskDepartmentWorkloadForbidden"),
            description="权限不足",
        ),
    },
)
