"""
任务统计相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema

from workorder.schema import standard_error_response, standard_success_response


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
