"""
性能监控和业务监控服务

提供API性能监控、业务指标统计、系统健康检查等功能
"""

import time
import psutil
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from functools import wraps
from django.db import connection
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.db.models import Count, Avg, Sum, Q, F
from django.http import JsonResponse

from ..models.core import WorkOrder, WorkOrderTask, WorkOrderProcess
from ..models.system import Notification, WorkOrderApprovalLog


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics = {}
        self.slow_query_threshold = getattr(settings, 'SLOW_QUERY_THRESHOLD', 1.0)  # 1秒
    
    def time_execution(self, name: str = None):
        """装饰器：监控执行时间"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    # 记录性能指标
                    metric_name = name or f"{func.__module__}.{func.__name__}"
                    self._record_execution_time(metric_name, execution_time)
                    
                    # 如果执行时间超过阈值，记录慢查询
                    if execution_time > self.slow_query_threshold:
                        self._record_slow_query(metric_name, execution_time, args, kwargs)
                    
                    return result
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    self._record_error(metric_name, execution_time, str(e))
                    raise
            
            return wrapper
        return decorator
    
    def _record_execution_time(self, name: str, execution_time: float) -> None:
        """记录执行时间"""
        timestamp = timezone.now().isoformat()
        
        # 存储到内存中（生产环境应该使用更持久化的存储）
        if 'execution_times' not in self.metrics:
            self.metrics['execution_times'] = []
        
        self.metrics['execution_times'].append({
            'name': name,
            'execution_time': execution_time,
            'timestamp': timestamp
        })
        
        # 保留最近1000条记录
        if len(self.metrics['execution_times']) > 1000:
            self.metrics['execution_times'] = self.metrics['execution_times'][-1000:]
        
        # 更新缓存
        cache.set(f'perf:{name}:last_execution', execution_time, 300)
        cache.set(f'perf:{name}:avg_execution', self._get_avg_execution_time(name), 300)
    
    def _record_slow_query(self, name: str, execution_time: float, args: tuple, kwargs: dict) -> None:
        """记录慢查询"""
        timestamp = timezone.now().isoformat()
        
        if 'slow_queries' not in self.metrics:
            self.metrics['slow_queries'] = []
        
        self.metrics['slow_queries'].append({
            'name': name,
            'execution_time': execution_time,
            'timestamp': timestamp,
            'args_count': len(args),
            'kwargs_count': len(kwargs),
            'traceback': self._get_traceback()
        })
        
        # 保留最近100条慢查询
        if len(self.metrics['slow_queries']) > 100:
            self.metrics['slow_queries'] = self.metrics['slow_queries'][-100:]
        
        # 发送告警（如果配置了）
        self._send_performance_alert(name, execution_time)
    
    def _record_error(self, name: str, execution_time: float, error: str) -> None:
        """记录错误"""
        timestamp = timezone.now().isoformat()
        
        if 'errors' not in self.metrics:
            self.metrics['errors'] = []
        
        self.metrics['errors'].append({
            'name': name,
            'execution_time': execution_time,
            'error': error,
            'timestamp': timestamp
        })
        
        # 保留最近100条错误
        if len(self.metrics['errors']) > 100:
            self.metrics['errors'] = self.metrics['errors'][-100:]
    
    def _get_avg_execution_time(self, name: str) -> float:
        """获取平均执行时间"""
        times = [m['execution_time'] for m in self.metrics.get('execution_times', []) if m['name'] == name]
        return sum(times) / len(times) if times else 0.0
    
    def _get_traceback(self) -> str:
        """获取调用栈"""
        import traceback
        return ''.join(traceback.format_stack()[-5:-1])
    
    def _send_performance_alert(self, name: str, execution_time: float) -> None:
        """发送性能告警"""
        if not getattr(settings, 'PERFORMANCE_ALERTS_ENABLED', False):
            return
        
        # 这里可以实现邮件、短信等告警方式
        print(f"PERFORMANCE ALERT: {name} took {execution_time:.2f}s")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        stats = {
            'total_requests': len(self.metrics.get('execution_times', [])),
            'slow_queries': len(self.metrics.get('slow_queries', [])),
            'errors': len(self.metrics.get('errors', [])),
            'avg_response_time': 0.0,
            'slowest_endpoints': [],
            'error_rate': 0.0
        }
        
        execution_times = self.metrics.get('execution_times', [])
        if execution_times:
            # 计算平均响应时间
            total_time = sum(m['execution_time'] for m in execution_times)
            stats['avg_response_time'] = total_time / len(execution_times)
            
            # 最慢的端点
            sorted_times = sorted(execution_times, key=lambda x: x['execution_time'], reverse=True)
            stats['slowest_endpoints'] = sorted_times[:10]
        
        # 计算错误率
        total_requests = stats['total_requests']
        total_errors = stats['errors']
        if total_requests > 0:
            stats['error_rate'] = (total_errors / total_requests) * 100
        
        return stats


class BusinessMetrics:
    """业务指标监控"""
    
    @staticmethod
    def get_workorder_metrics(time_range: str = '24h') -> Dict[str, Any]:
        """获取施工单业务指标"""
        now = timezone.now()
        
        if time_range == '24h':
            start_time = now - timedelta(hours=24)
        elif time_range == '7d':
            start_time = now - timedelta(days=7)
        elif time_range == '30d':
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(hours=24)
        
        queryset = WorkOrder.objects.filter(created_at__gte=start_time)
        
        # 基础指标
        total_orders = queryset.count()
        completed_orders = queryset.filter(status='completed').count()
        pending_orders = queryset.filter(status='pending').count()
        in_progress_orders = queryset.filter(status='in_progress').count()
        
        # 审核指标
        approved_orders = queryset.filter(approval_status='approved').count()
        rejected_orders = queryset.filter(approval_status='rejected').count()
        
        # 金额指标
        total_amount = queryset.aggregate(total=Sum('total_amount'))['total'] or 0
        avg_amount = queryset.aggregate(avg=Avg('total_amount'))['avg'] or 0
        
        # 优先级分布
        priority_stats = queryset.values('priority').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # 时间相关指标
        avg_completion_time = BusinessMetrics._calculate_avg_completion_time(queryset)
        
        return {
            'time_range': time_range,
            'period': {
                'start': start_time.isoformat(),
                'end': now.isoformat()
            },
            'order_stats': {
                'total': total_orders,
                'completed': completed_orders,
                'pending': pending_orders,
                'in_progress': in_progress_orders,
                'completion_rate': (completed_orders / total_orders * 100) if total_orders > 0 else 0
            },
            'approval_stats': {
                'approved': approved_orders,
                'rejected': rejected_orders,
                'pending': queryset.filter(approval_status='pending').count(),
                'approval_rate': (approved_orders / (approved_orders + rejected_orders) * 100) if (approved_orders + rejected_orders) > 0 else 0
            },
            'amount_stats': {
                'total': float(total_amount),
                'average': float(avg_amount)
            },
            'priority_distribution': list(priority_stats),
            'time_metrics': {
                'avg_completion_days': avg_completion_time,
                'orders_overdue': queryset.filter(deadline__lt=now, status__in=['pending', 'in_progress']).count()
            }
        }
    
    @staticmethod
    def get_task_metrics(time_range: str = '24h') -> Dict[str, Any]:
        """获取任务业务指标"""
        now = timezone.now()
        
        if time_range == '24h':
            start_time = now - timedelta(hours=24)
        elif time_range == '7d':
            start_time = now - timedelta(days=7)
        else:
            start_time = now - timedelta(hours=24)
        
        queryset = WorkOrderTask.objects.filter(created_at__gte=start_time)
        
        # 基础指标
        total_tasks = queryset.count()
        completed_tasks = queryset.filter(status='completed').count()
        pending_tasks = queryset.filter(status='pending').count()
        in_progress_tasks = queryset.filter(status='in_progress').count()
        
        # 用户指标
        user_stats = queryset.values('assigned_to__username').annotate(
            total_tasks=Count('id'),
            completed_tasks=Count('id', filter=Q(status='completed')),
            avg_completion_time=Avg('completed_at') - Avg('started_at')
        ).order_by('-total_tasks')[:10]
        
        # 超时任务
        overdue_tasks = queryset.filter(
            deadline__lt=now,
            status__in=['pending', 'in_progress']
        ).count()
        
        return {
            'time_range': time_range,
            'task_stats': {
                'total': total_tasks,
                'completed': completed_tasks,
                'pending': pending_tasks,
                'in_progress': in_progress_tasks,
                'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            },
            'user_performance': list(user_stats),
            'time_metrics': {
                'overdue_tasks': overdue_tasks,
                'overdue_rate': (overdue_tasks / total_tasks * 100) if total_tasks > 0 else 0
            }
        }
    
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """获取系统指标"""
        # 数据库连接数
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                db_connections = cursor.fetchone()[0]
        except:
            db_connections = 0
        
        # 系统资源使用情况
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 缓存指标
        cache_info = {
            'redis_available': False,
            'hits': 0,
            'misses': 0
        }
        
        try:
            # 尝试获取Redis信息（如果使用Redis缓存）
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            info = r.info()
            cache_info.update({
                'redis_available': True,
                'used_memory': info['used_memory'],
                'max_memory': info['maxmemory'],
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0)
            })
        except:
            pass
        
        return {
            'timestamp': timezone.now().isoformat(),
            'database': {
                'connections': db_connections,
                'max_connections': getattr(settings, 'DATABASES', {}).get('default', {}).get('CONN_MAX_AGE', 0)
            },
            'system_resources': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used': memory.used,
                'memory_total': memory.total,
                'disk_used': disk.used,
                'disk_total': disk.total,
                'disk_percent': (disk.used / disk.total) * 100
            },
            'cache': cache_info,
            'django_settings': {
                'debug': settings.DEBUG,
                'allowed_hosts': getattr(settings, 'ALLOWED_HOSTS', []),
                'timezone': settings.TIME_ZONE
            }
        }
    
    @staticmethod
    def _calculate_avg_completion_time(queryset) -> float:
        """计算平均完成时间"""
        completed_orders = queryset.filter(status='completed').exclude(
            completed_at__isnull=True,
            created_at__isnull=True
        )
        
        if not completed_orders.exists():
            return 0.0
        
        total_days = 0
        for order in completed_orders:
            if order.completed_at and order.created_at:
                days = (order.completed_at.date() - order.created_at.date()).days
                total_days += days
        
        return total_days / completed_orders.count()


class MonitoringService:
    """监控服务"""
    
    def __init__(self):
        self.performance_monitor = PerformanceMonitor()
        self.business_metrics = BusinessMetrics()
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'checks': {}
        }
        
        # 检查数据库连接
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_status['checks']['database'] = {'status': 'ok', 'response_time': 0.1}
        except Exception as e:
            health_status['checks']['database'] = {'status': 'error', 'error': str(e)}
            health_status['status'] = 'unhealthy'
        
        # 检查缓存
        try:
            cache.set('health_check', 'ok', 10)
            cache.get('health_check')
            health_status['checks']['cache'] = {'status': 'ok'}
        except Exception as e:
            health_status['checks']['cache'] = {'status': 'error', 'error': str(e)}
            health_status['status'] = 'degraded'
        
        # 检查系统资源
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            if cpu_percent > 90 or memory.percent > 90:
                health_status['checks']['system_resources'] = {
                    'status': 'warning',
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent
                }
                if health_status['status'] == 'healthy':
                    health_status['status'] = 'degraded'
            else:
                health_status['checks']['system_resources'] = {
                    'status': 'ok',
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent
                }
        except Exception as e:
            health_status['checks']['system_resources'] = {'status': 'error', 'error': str(e)}
            health_status['status'] = 'unhealthy'
        
        return health_status
    
    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """获取仪表板指标"""
        return {
            'performance': self.performance_monitor.get_performance_stats(),
            'business_workorder': self.business_metrics.get_workorder_metrics('24h'),
            'business_task': self.business_metrics.get_task_metrics('24h'),
            'system': self.business_metrics.get_system_metrics(),
            'health': self.health_check()
        }


# 全局监控实例
monitoring_service = MonitoringService()