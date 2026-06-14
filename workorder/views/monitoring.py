"""
监控相关视图集

提供性能监控、业务指标、系统健康检查等API
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from ..response import APIResponse
from workorder.docs.monitoring import (
    alert_settings_docs,
    alerts_docs,
    dashboard_docs,
    error_logs_docs,
    execution_times_docs,
    health_check_docs,
    overview_docs,
    performance_stats_docs,
    productivity_trends_docs,
    quality_metrics_docs,
    resource_usage_docs,
    slow_queries_docs,
    system_metrics_docs,
    task_metrics_docs,
    update_alert_settings_docs,
    user_performance_docs,
    workorder_metrics_docs,
)
from ..services.monitoring import (
    BusinessMetrics,
    MonitoringStatsService,
    monitoring_service,
)


class PerformanceMonitoringViewSet(viewsets.GenericViewSet):
    """性能监控视图集"""

    permission_classes = [IsAdminUser]

    @action(detail=False, methods=["get"])
    @performance_stats_docs
    def performance_stats(self, request):
        """获取性能统计"""
        stats = monitoring_service.performance_monitor.get_performance_stats()
        return APIResponse.success(data=stats, message="性能统计获取成功")

    @action(detail=False, methods=["get"])
    @slow_queries_docs
    def slow_queries(self, request):
        """获取慢查询列表"""
        slow_queries = monitoring_service.performance_monitor.metrics.get(
            "slow_queries", []
        )
        return APIResponse.success(data=slow_queries, message="慢查询列表获取成功")

    @action(detail=False, methods=["get"])
    @error_logs_docs
    def error_logs(self, request):
        """获取错误日志"""
        errors = monitoring_service.performance_monitor.metrics.get("errors", [])
        return APIResponse.success(data=errors, message="错误日志获取成功")

    @action(detail=False, methods=["get"])
    @execution_times_docs
    def execution_times(self, request):
        """获取执行时间统计"""
        execution_times = monitoring_service.performance_monitor.metrics.get(
            "execution_times", []
        )
        endpoint_list = MonitoringStatsService.get_execution_time_stats(execution_times)
        return APIResponse.success(data=endpoint_list, message="执行时间统计获取成功")


class BusinessMetricsViewSet(viewsets.GenericViewSet):
    """业务指标视图集"""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    @workorder_metrics_docs
    def workorder_metrics(self, request):
        """获取施工单业务指标"""
        time_range = request.query_params.get("time_range", "24h")
        metrics = BusinessMetrics.get_workorder_metrics(time_range)
        return APIResponse.success(data=metrics, message="施工单业务指标获取成功")

    @action(detail=False, methods=["get"])
    @task_metrics_docs
    def task_metrics(self, request):
        """获取任务业务指标"""
        time_range = request.query_params.get("time_range", "24h")
        metrics = BusinessMetrics.get_task_metrics(time_range)
        return APIResponse.success(data=metrics, message="任务业务指标获取成功")

    @action(detail=False, methods=["get"], permission_classes=[IsAdminUser])
    @user_performance_docs
    def user_performance(self, request):
        """获取用户绩效指标"""
        data = MonitoringStatsService.get_user_performance(days=30)
        return APIResponse.success(data=data, message="用户绩效指标获取成功")

    @action(detail=False, methods=["get"])
    @productivity_trends_docs
    def productivity_trends(self, request):
        """获取生产力趋势"""
        data = MonitoringStatsService.get_productivity_trends(days=7)
        return APIResponse.success(data=data, message="生产力趋势获取成功")

    @action(detail=False, methods=["get"])
    @quality_metrics_docs
    def quality_metrics(self, request):
        """获取质量指标"""
        data = MonitoringStatsService.get_quality_metrics(days=30)
        return APIResponse.success(data=data, message="质量指标获取成功")

    @action(detail=False, methods=["get"])
    def operations_dashboard(self, request):
        """运营仪表盘：展示未分派任务、待采购、待质检、待入库、待收款等关键指标"""
        data = MonitoringStatsService.get_operations_dashboard()
        return APIResponse.success(data=data)


class SystemMonitoringViewSet(viewsets.GenericViewSet):
    """系统监控视图集"""

    permission_classes = [IsAdminUser]

    @action(detail=False, methods=["get"])
    @system_metrics_docs
    def system_metrics(self, request):
        """获取系统指标"""
        metrics = BusinessMetrics.get_system_metrics()
        return APIResponse.success(data=metrics, message="系统指标获取成功")

    @action(detail=False, methods=["get"])
    @health_check_docs
    def health_check(self, request):
        """系统健康检查"""
        health = monitoring_service.health_check()

        http_status = 200
        if health["status"] == "unhealthy":
            http_status = 503
        elif health["status"] == "degraded":
            http_status = 200

        return APIResponse.success(
            data=health, message="健康检查完成", code=http_status
        )

    @action(detail=False, methods=["get"])
    @resource_usage_docs
    def resource_usage(self, request):
        """获取资源使用情况"""
        data = MonitoringStatsService.get_resource_usage()
        return APIResponse.success(data=data, message="资源使用情况获取成功")

    @action(detail=False, methods=["get"])
    @alert_settings_docs
    def alert_settings(self, request):
        """获取告警设置"""
        data = MonitoringStatsService.get_alert_settings()
        return APIResponse.success(data=data, message="告警设置获取成功")

    @action(detail=False, methods=["post"])
    @update_alert_settings_docs
    def update_alert_settings(self, request):
        """更新告警设置"""
        # 这里可以实现告警设置的更新逻辑
        return APIResponse.success(message="告警设置更新成功")

    @action(detail=False, methods=["get"])
    def data_consistency(self, request):
        """数据一致性检查"""
        from ..services.data_consistency_service import DataConsistencyService

        result = DataConsistencyService.run_all_checks()
        return APIResponse.success(data=result)


class DashboardMonitoringViewSet(viewsets.GenericViewSet):
    """仪表板监控视图集"""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    @overview_docs
    def overview(self, request):
        """获取监控概览"""
        dashboard_data = monitoring_service.get_dashboard_metrics()
        return APIResponse.success(data=dashboard_data, message="监控概览获取成功")

    @action(detail=False, methods=["get"])
    @alerts_docs
    def alerts(self, request):
        """获取当前告警"""
        alerts = MonitoringStatsService.get_alerts()
        return APIResponse.success(data=alerts, message="告警列表获取成功")
