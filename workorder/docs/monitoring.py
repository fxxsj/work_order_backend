"""
监控与统计相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from workorder.schema import standard_success_response


performance_stats_docs = extend_schema(
    tags=["统计"],
    summary="获取性能统计",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("PerformanceStatsResponse"),
            description="性能统计",
            examples=[
                OpenApiExample(
                    name="示例响应",
                    summary="性能统计",
                    value={
                        "success": True,
                        "code": 200,
                        "message": "操作成功",
                        "data": {
                            "avg_response_ms": 120,
                            "p95_response_ms": 280,
                            "requests": 1024,
                        },
                        "timestamp": "2026-03-02T09:00:00+08:00",
                    },
                    response_only=True,
                )
            ],
        )
    },
)

slow_queries_docs = extend_schema(
    tags=["统计"],
    summary="获取慢查询列表",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("SlowQueriesResponse"),
            description="慢查询列表",
        )
    },
)

error_logs_docs = extend_schema(
    tags=["统计"],
    summary="获取错误日志",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ErrorLogsResponse"),
            description="错误日志",
        )
    },
)

execution_times_docs = extend_schema(
    tags=["统计"],
    summary="获取执行时间统计",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ExecutionTimesResponse"),
            description="执行时间统计",
        )
    },
)

workorder_metrics_docs = extend_schema(
    tags=["统计"],
    summary="获取施工单业务指标",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("WorkOrderMetricsResponse"),
            description="施工单业务指标",
        )
    },
)

task_metrics_docs = extend_schema(
    tags=["统计"],
    summary="获取任务业务指标",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("TaskMetricsResponse"),
            description="任务业务指标",
        )
    },
)

user_performance_docs = extend_schema(
    tags=["统计"],
    summary="获取用户绩效指标",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("UserPerformanceMetricsResponse"),
            description="用户绩效指标",
        )
    },
)

productivity_trends_docs = extend_schema(
    tags=["统计"],
    summary="获取生产力趋势",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ProductivityTrendsResponse"),
            description="生产力趋势",
        )
    },
)

quality_metrics_docs = extend_schema(
    tags=["统计"],
    summary="获取质量指标",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("QualityMetricsResponse"),
            description="质量指标",
        )
    },
)

system_metrics_docs = extend_schema(
    tags=["统计"],
    summary="获取系统指标",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("SystemMetricsResponse"),
            description="系统指标",
        )
    },
)

health_check_docs = extend_schema(
    tags=["统计"],
    summary="系统健康检查",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("HealthCheckResponse"),
            description="健康检查",
        ),
        503: OpenApiResponse(
            response=standard_success_response("HealthCheckUnhealthyResponse"),
            description="不健康",
        ),
    },
)

resource_usage_docs = extend_schema(
    tags=["统计"],
    summary="获取资源使用情况",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ResourceUsageResponse"),
            description="资源使用情况",
        )
    },
)

alert_settings_docs = extend_schema(
    tags=["统计"],
    summary="获取告警设置",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("AlertSettingsResponse"),
            description="告警设置",
        )
    },
)

update_alert_settings_docs = extend_schema(
    tags=["统计"],
    summary="更新告警设置",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("AlertSettingsUpdateResponse"),
            description="更新成功",
        )
    },
)

dashboard_docs = extend_schema(
    tags=["统计"],
    summary="获取监控概览",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("MonitoringDashboardResponse"),
            description="监控概览",
        )
    },
)

overview_docs = extend_schema(
    tags=["统计"],
    summary="获取监控概览",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("MonitoringOverviewResponse"),
            description="监控概览",
        )
    },
)

alerts_docs = extend_schema(
    tags=["统计"],
    summary="获取告警列表",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("AlertsResponse"),
            description="告警列表",
        )
    },
)
