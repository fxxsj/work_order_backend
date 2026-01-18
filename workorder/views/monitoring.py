"""
监控相关视图集

提供性能监控、业务指标、系统健康检查等API
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from django.contrib.auth.models import User

from ..services.monitoring import (
    monitoring_service, PerformanceMonitor, BusinessMetrics
)
from ..services.api_gateway import APIResponse


class PerformanceMonitoringViewSet(viewsets.GenericViewSet):
    """性能监控视图集"""
    permission_classes = [IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def performance_stats(self, request):
        """获取性能统计"""
        stats = monitoring_service.performance_monitor.get_performance_stats()
        return APIResponse.success(data=stats, message='性能统计获取成功')
    
    @action(detail=False, methods=['get'])
    def slow_queries(self, request):
        """获取慢查询列表"""
        slow_queries = monitoring_service.performance_monitor.metrics.get('slow_queries', [])
        return APIResponse.success(data=slow_queries, message='慢查询列表获取成功')
    
    @action(detail=False, methods=['get'])
    def error_logs(self, request):
        """获取错误日志"""
        errors = monitoring_service.performance_monitor.metrics.get('errors', [])
        return APIResponse.success(data=errors, message='错误日志获取成功')
    
    @action(detail=False, methods=['get'])
    def execution_times(self, request):
        """获取执行时间统计"""
        execution_times = monitoring_service.performance_monitor.metrics.get('execution_times', [])
        
        # 按端点分组统计
        endpoint_stats = {}
        for execution in execution_times:
            name = execution['name']
            if name not in endpoint_stats:
                endpoint_stats[name] = {
                    'count': 0,
                    'total_time': 0.0,
                    'min_time': float('inf'),
                    'max_time': 0.0,
                    'avg_time': 0.0
                }
            
            stats = endpoint_stats[name]
            stats['count'] += 1
            stats['total_time'] += execution['execution_time']
            stats['min_time'] = min(stats['min_time'], execution['execution_time'])
            stats['max_time'] = max(stats['max_time'], execution['execution_time'])
            stats['avg_time'] = stats['total_time'] / stats['count']
        
        # 转换为列表并按平均时间排序
        endpoint_list = []
        for name, stats in endpoint_stats.items():
            endpoint_list.append({
                'endpoint': name,
                **stats
            })
        
        endpoint_list.sort(key=lambda x: x['avg_time'], reverse=True)
        
        return APIResponse.success(data=endpoint_list, message='执行时间统计获取成功')


class BusinessMetricsViewSet(viewsets.GenericViewSet):
    """业务指标视图集"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def workorder_metrics(self, request):
        """获取施工单业务指标"""
        time_range = request.query_params.get('time_range', '24h')
        metrics = BusinessMetrics.get_workorder_metrics(time_range)
        return APIResponse.success(data=metrics, message='施工单业务指标获取成功')
    
    @action(detail=False, methods=['get'])
    def task_metrics(self, request):
        """获取任务业务指标"""
        time_range = request.query_params.get('time_range', '24h')
        metrics = BusinessMetrics.get_task_metrics(time_range)
        return APIResponse.success(data=metrics, message='任务业务指标获取成功')
    
    @action(detail=False, methods=['get'])
    def user_performance(self, request):
        """获取用户绩效指标"""
        from datetime import timedelta
        
        # 获取最近30天的用户绩效
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        from ..models.core import WorkOrderTask
        user_stats = WorkOrderTask.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).values('assigned_to__username').annotate(
            total_tasks=Count('id'),
            completed_tasks=Count('id', filter=models.Q(status='completed')),
            avg_completion_time=Avg(F('completed_at') - F('started_at'))
        ).filter(
            assigned_to__is_active=True
        ).order_by('-completed_tasks')[:20]
        
        return APIResponse.success(data=list(user_stats), message='用户绩效指标获取成功')
    
    @action(detail=False, methods=['get'])
    def productivity_trends(self, request):
        """获取生产力趋势"""
        from datetime import timedelta
        
        # 获取最近7天的每日数据
        daily_data = []
        for i in range(7):
            date = (timezone.now() - timedelta(days=i)).date()
            
            # 当天的施工单完成数
            from ..models.core import WorkOrder
            completed_orders = WorkOrder.objects.filter(
                completed_at__date=date
            ).count()
            
            # 当天的任务完成数
            from ..models.core import WorkOrderTask
            completed_tasks = WorkOrderTask.objects.filter(
                completed_at__date=date
            ).count()
            
            daily_data.append({
                'date': date.isoformat(),
                'completed_orders': completed_orders,
                'completed_tasks': completed_tasks
            })
        
        return APIResponse.success(data=reversed(daily_data), message='生产力趋势获取成功')
    
    @action(detail=False, methods=['get'])
    def quality_metrics(self, request):
        """获取质量指标"""
        from datetime import timedelta
        from ..models.core import WorkOrderTask
        
        # 获取最近30天的质量数据
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        # 不良品统计
        tasks_with_defects = WorkOrderTask.objects.filter(
            created_at__gte=start_date,
            defective_quantity__gt=0
        ).aggregate(
            total_tasks=Count('id'),
            total_defects=Sum('defective_quantity'),
            total_completed=Sum('completed_quantity')
        )
        
        total_tasks = tasks_with_defects['total_tasks'] or 0
        total_defects = tasks_with_defects['total_defects'] or 0
        total_completed = tasks_with_defects['total_completed'] or 0
        
        # 计算质量指标
        defect_rate = (total_defects / total_completed * 100) if total_completed > 0 else 0
        
        quality_metrics = {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'defect_stats': {
                'total_tasks_with_defects': total_tasks,
                'total_defects': total_defects,
                'total_completed': total_completed,
                'defect_rate': round(defect_rate, 2)
            },
            'quality_score': round(100 - defect_rate, 2)  # 质量分数
        }
        
        return APIResponse.success(data=quality_metrics, message='质量指标获取成功')


class SystemMonitoringViewSet(viewsets.GenericViewSet):
    """系统监控视图集"""
    permission_classes = [IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def system_metrics(self, request):
        """获取系统指标"""
        metrics = BusinessMetrics.get_system_metrics()
        return APIResponse.success(data=metrics, message='系统指标获取成功')
    
    @action(detail=False, methods=['get'])
    def health_check(self, request):
        """系统健康检查"""
        health = monitoring_service.health_check()
        
        # 根据健康状态返回不同的HTTP状态码
        http_status = 200
        if health['status'] == 'unhealthy':
            http_status = 503
        elif health['status'] == 'degraded':
            http_status = 200  # 或者可以设置为206
        
        return APIResponse.success(data=health, message='健康检查完成', code=http_status)
    
    @action(detail=False, methods=['get'])
    def resource_usage(self, request):
        """获取资源使用情况"""
        import psutil
        
        # CPU使用率（历史数据）
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存使用情况
        memory = psutil.virtual_memory()
        
        # 磁盘使用情况
        disk = psutil.disk_usage('/')
        
        # 网络I/O统计
        try:
            network = psutil.net_io_counters()
            network_stats = {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            }
        except:
            network_stats = {}
        
        resource_data = {
            'timestamp': timezone.now().isoformat(),
            'cpu': {
                'percent': cpu_percent,
                'count': psutil.cpu_count()
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'percent': memory.percent
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': (disk.used / disk.total) * 100
            },
            'network': network_stats,
            'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else []
        }
        
        return APIResponse.success(data=resource_data, message='资源使用情况获取成功')
    
    @action(detail=False, methods=['get'])
    def alert_settings(self, request):
        """获取告警设置"""
        from django.conf import settings
        
        alert_settings = {
            'performance_alerts': {
                'enabled': getattr(settings, 'PERFORMANCE_ALERTS_ENABLED', False),
                'slow_query_threshold': getattr(settings, 'SLOW_QUERY_THRESHOLD', 1.0),
                'error_rate_threshold': getattr(settings, 'ERROR_RATE_THRESHOLD', 5.0),
                'cpu_threshold': getattr(settings, 'CPU_ALERT_THRESHOLD', 80.0),
                'memory_threshold': getattr(settings, 'MEMORY_ALERT_THRESHOLD', 80.0),
                'disk_threshold': getattr(settings, 'DISK_ALERT_THRESHOLD', 80.0)
            },
            'business_alerts': {
                'enabled': getattr(settings, 'BUSINESS_ALERTS_ENABLED', False),
                'overdue_orders_threshold': getattr(settings, 'OVERDUE_ORDERS_THRESHOLD', 5),
                'defect_rate_threshold': getattr(settings, 'DEFECT_RATE_THRESHOLD', 5.0),
                'completion_rate_threshold': getattr(settings, 'COMPLETION_RATE_THRESHOLD', 80.0)
            },
            'notification_channels': {
                'email': getattr(settings, 'ALERT_EMAIL_ENABLED', True),
                'sms': getattr(settings, 'ALERT_SMS_ENABLED', False),
                'webhook': getattr(settings, 'ALERT_WEBHOOK_ENABLED', False),
                'webhook_url': getattr(settings, 'ALERT_WEBHOOK_URL', '')
            }
        }
        
        return APIResponse.success(data=alert_settings, message='告警设置获取成功')
    
    @action(detail=False, methods=['post'])
    def update_alert_settings(self, request):
        """更新告警设置"""
        # 这里可以实现告警设置的更新逻辑
        # 为了演示，暂时返回成功响应
        return APIResponse.success(message='告警设置更新成功')


class DashboardMonitoringViewSet(viewsets.GenericViewSet):
    """仪表板监控视图集"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """获取监控概览"""
        dashboard_data = monitoring_service.get_dashboard_metrics()
        return APIResponse.success(data=dashboard_data, message='监控概览获取成功')
    
    @action(detail=False, methods=['get'])
    def alerts(self, request):
        """获取当前告警"""
        alerts = []
        
        # 检查性能告警
        performance_stats = monitoring_service.performance_monitor.get_performance_stats()
        if performance_stats['error_rate'] > 5.0:  # 错误率超过5%
            alerts.append({
                'type': 'performance',
                'level': 'warning',
                'message': f'系统错误率过高: {performance_stats["error_rate"]:.2f}%',
                'timestamp': timezone.now().isoformat()
            })
        
        # 检查系统资源告警
        system_metrics = BusinessMetrics.get_system_metrics()
        resources = system_metrics['system_resources']
        
        if resources['cpu_percent'] > 80:
            alerts.append({
                'type': 'resource',
                'level': 'warning',
                'message': f'CPU使用率过高: {resources["cpu_percent"]:.1f}%',
                'timestamp': timezone.now().isoformat()
            })
        
        if resources['memory_percent'] > 80:
            alerts.append({
                'type': 'resource',
                'level': 'warning',
                'message': f'内存使用率过高: {resources["memory_percent"]:.1f}%',
                'timestamp': timezone.now().isoformat()
            })
        
        # 检查业务告警
        workorder_metrics = BusinessMetrics.get_workorder_metrics('24h')
        overdue_orders = workorder_metrics['time_metrics']['orders_overdue']
        
        if overdue_orders > 5:  # 逾期订单超过5个
            alerts.append({
                'type': 'business',
                'level': 'warning',
                'message': f'逾期订单过多: {overdue_orders}个',
                'timestamp': timezone.now().isoformat()
            })
        
        return APIResponse.success(data=alerts, message='告警列表获取成功')


# 导入必要的模型
from django.db import models