"""
P2 优化: 性能监控和告警系统
实现全面的系统监控，包括性能监控、错误监控、业务指标监控和告警机制
"""
import time
import logging
import psutil
import logging
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.management.base import BaseCommand
import json

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        try:
            from django.core.cache import cache
            self.redis_client = cache._cache.get_client()
        except ImportError:
            logger.warning("Redis not available, using mock client")
            self.redis_client = None
        except Exception as e:
            logger.error(f"Error initializing performance monitor: {e}")
            self.redis_client = None
    
    def get_system_metrics(self):
        """获取系统性能指标"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            memory_info = {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'percent': memory.percent
            }
            
            # 磁盘使用情况
            disk = psutil.disk_usage('/')
            disk_info = {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': (disk.used / disk.total) * 100
            }
            
            # 网络连接数
            network = psutil.net_connections()
            
            return {
                'cpu_percent': cpu_percent,
                'memory': memory_info,
                'disk': disk_info,
                'network_connections': len(network),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return None
    
    def get_database_metrics(self):
        """获取数据库性能指标"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                # 获取连接数
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                active_connections = cursor.fetchone()[0]
                
                # 获取数据库大小
                cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                db_size = cursor.fetchone()[0]
                
                return {
                    'active_connections': active_connections,
                    'database_size': db_size,
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error getting database metrics: {e}")
            return None
    
    def get_cache_metrics(self):
        """获取缓存性能指标"""
        if not self.redis_client:
            return None
            
        try:
            info = self.redis_client.info()
            return {
                'used_memory': info['used_memory_human'],
                'connected_clients': info.get('connected_clients'),
                'total_commands_processed': info['total_commands_processed'],
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': self._calculate_hit_rate(info),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting cache metrics: {e}")
            return None
    
    def _calculate_hit_rate(self, info):
        """计算缓存命中率"""
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses
        if total == 0:
            return 0
        return (hits / total) * 100
    
    def get_application_metrics(self):
        """获取应用性能指标"""
        try:
            # 从缓存获取应用指标
            metrics_data = cache.get('app_performance_metrics') or {}
            
            # 计算响应时间统计
            response_times = metrics_data.get('response_times', [])
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                max_response_time = max(response_times)
                min_response_time = min(response_times)
            else:
                avg_response_time = max_response_time = min_response_time = 0
            
            # 获取错误率
            error_count = metrics_data.get('error_count', 0)
            total_requests = metrics_data.get('total_requests', 0)
            error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
            
            # 获取活跃用户数
            active_users = metrics_data.get('active_users', 0)
            
            return {
                'avg_response_time': avg_response_time,
                'max_response_time': max_response_time,
                'min_response_time': min_response_time,
                'error_rate': error_rate,
                'total_requests': total_requests,
                'error_count': error_count,
                'active_users': active_users,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting application metrics: {e}")
            return None
    
    def record_response_time(self, response_time):
        """记录API响应时间"""
        try:
            metrics_data = cache.get('app_performance_metrics') or {}
            response_times = metrics_data.get('response_times', [])
            
            # 只保留最近1000次请求的响应时间
            response_times.append(response_time)
            if len(response_times) > 1000:
                response_times = response_times[-1000:]
            
            metrics_data['response_times'] = response_times
            cache.set('app_performance_metrics', metrics_data, timeout=300)
        except Exception as e:
            logger.error(f"Error recording response time: {e}")
    
    def record_error(self):
        """记录错误"""
        try:
            metrics_data = cache.get('app_performance_metrics') or {}
            metrics_data['error_count'] = metrics_data.get('error_count', 0) + 1
            cache.set('app_performance_metrics', metrics_data, timeout=300)
        except Exception as e:
            logger.error(f"Error recording error: {e}")
    
    def record_request(self):
        """记录请求"""
        try:
            metrics_data = cache.get('app_performance_metrics') or {}
            metrics_data['total_requests'] = metrics_data.get('total_requests', 0) + 1
            cache.set('app_performance_metrics', metrics_data, timeout=300)
        except Exception as e:
            logger.error(f"Error recording request: {e}")
    
    def update_active_users(self, user_count):
        """更新活跃用户数"""
        try:
            metrics_data = cache.get('app_performance_metrics') or {}
            metrics_data['active_users'] = user_count
            cache.set('app_performance_metrics', metrics_data, timeout=300)
        except Exception as e:
            logger.error(f"Error updating active users: {e}")


class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self.alert_rules = self._load_alert_rules()
    
    def _load_alert_rules(self):
        """加载告警规则"""
        return {
            'cpu_threshold': 80,  # CPU使用率超过80%
            'memory_threshold': 85,  # 内存使用率超过85%
            'disk_threshold': 90,  # 磁盘使用率超过90%
            'error_rate_threshold': 5,  # 错误率超过5%
            'response_time_threshold': 2000,  # 平均响应时间超过2秒
            'database_connections_threshold': 80,  # 数据库连接数超过80
        }
    
    def check_system_alerts(self, metrics):
        """检查系统告警"""
        alerts = []
        rules = self.alert_rules
        
        # CPU告警
        if metrics and metrics.get('cpu_percent', 0) > rules['cpu_threshold']:
            alerts.append({
                'type': 'system',
                'level': 'warning',
                'message': f"CPU使用率过高: {metrics['cpu_percent']}%",
                'timestamp': datetime.now().isoformat()
            })
        
        # 内存告警
        if metrics and metrics.get('memory', {}).get('percent', 0) > rules['memory_threshold']:
            alerts.append({
                'type': 'system',
                'level': 'warning',
                'message': f"内存使用率过高: {metrics['memory']['percent']}%",
                'timestamp': datetime.now().isoformat()
            })
        
        # 磁盘告警
        if metrics and metrics.get('disk', {}).get('percent', 0) > rules['disk_threshold']:
            alerts.append({
                'type': 'system',
                'level': 'critical',
                'message': f"磁盘使用率过高: {metrics['disk']['percent']}%",
                'timestamp': datetime.now().isoformat()
            })
        
        return alerts
    
    def check_application_alerts(self, metrics):
        """检查应用告警"""
        alerts = []
        rules = self.alert_rules
        
        # 错误率告警
        if metrics and metrics.get('error_rate', 0) > rules['error_rate_threshold']:
            alerts.append({
                'type': 'application',
                'level': 'error',
                'message': f"错误率过高: {metrics['error_rate']}%",
                'timestamp': datetime.now().isoformat()
            })
        
        # 响应时间告警
        if metrics and metrics.get('avg_response_time', 0) > rules['response_time_threshold']:
            alerts.append({
                'type': 'application',
                'level': 'warning',
                'message': f"平均响应时间过长: {metrics['avg_response_time']}ms",
                'timestamp': datetime.now().isoformat()
            })
        
        return alerts
    
    def check_database_alerts(self, metrics):
        """检查数据库告警"""
        alerts = []
        rules = self.alert_rules
        
        # 数据库连接数告警
        if metrics and metrics.get('active_connections', 0) > rules['database_connections_threshold']:
            alerts.append({
                'type': 'database',
                'level': 'warning',
                'message': f"数据库连接数过多: {metrics['active_connections']}",
                'timestamp': datetime.now().isoformat()
            })
        
        return alerts
    
    def send_alert(self, alert):
        """发送告警"""
        try:
            # 记录告警到日志
            level = alert['level'].upper()
            logger.log(getattr(logging, level), f"ALERT: {alert['message']}")
            
            # 发送到缓存（用于Web界面显示）
            if self.redis_client:
                alerts_key = f"alerts_{datetime.now().strftime('%Y%m%d')}"
                existing_alerts = cache.get(alerts_key, [])
                existing_alerts.append(alert)
                
                # 只保留最近100个告警
                if len(existing_alerts) > 100:
                    existing_alerts = existing_alerts[-100:]
                
                cache.set(alerts_key, existing_alerts, timeout=86400)  # 24小时
            
            # 这里可以扩展为发送邮件、短信等通知
            self._send_notification(alert)
            
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
    
    def _send_notification(self, alert):
        """发送通知（可以扩展为邮件、短信等）"""
        # 示例：发送邮件通知
        logger.info(f"Notification sent for alert: {alert}")
        
        # 示例：发送邮件通知
        # if alert['level'] in ['critical', 'error']:
        #     self._send_email_alert(alert)
    
    def get_recent_alerts(self, hours=24):
        """获取最近的告警"""
        try:
            if self.redis_client:
                alerts_key = f"alerts_{datetime.now().strftime('%Y%m%d')}"
                all_alerts = cache.get(alerts_key, [])
                
                # 过滤指定时间范围内的告警
                cutoff_time = datetime.now() - timedelta(hours=hours)
                recent_alerts = [
                    alert for alert in all_alerts
                    if datetime.fromisoformat(alert['timestamp']) > cutoff_time
                ]
                
                return recent_alerts
        except Exception as e:
            logger.error(f"Error getting recent alerts: {e}")
            return None


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """性能监控中间件"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.performance_monitor = PerformanceMonitor()
        self.alert_manager = AlertManager()
    
    def process_request(self, request):
        """处理请求"""
        request.start_time = time.time()
        request.start_date = datetime.now()
        return None
    
    def process_response(self, request, response):
        """处理响应"""
        try:
            # 计算响应时间
            if hasattr(request, 'start_time'):
                response_time = int((time.time() - request.start_time) * 1000)
                
                # 记录响应时间
                self.performance_monitor.record_response_time(response_time)
            
            # 记录请求
            self.performance_monitor.record_request()
            
            # 检查响应状态
            if response.status_code >= 400:
                self.performance_monitor.record_error()
            
            return response
        except Exception as e:
            logger.error(f"Error in performance middleware: {e}")
            return response


class Command(BaseCommand):
    """收集性能指标的命令"""
    
    help = 'Collect performance metrics and check for alerts'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--check-alerts',
            action='store_true',
            help='Check for alerts and send notifications'
        )
        
        parser.add_argument(
            '--output-file',
            type=str,
            help='Output metrics to JSON file'
        )
    
    def handle(self, *args, **options):
        """处理命令"""
        performance_monitor = PerformanceMonitor()
        alert_manager = AlertManager()
        
        # 收集所有指标
        system_metrics = performance_monitor.get_system_metrics()
        database_metrics = performance_monitor.get_database_metrics()
        cache_metrics = performance_monitor.get_cache_metrics()
        application_metrics = performance_monitor.get_application_metrics()
        
        # 收集业务指标
        business_metrics = None
        if performance_monitor.redis_client:
            business_metrics = performance_monitor.get_workorder_metrics()
            user_metrics = performance_monitor.get_user_activity_metrics()
        
        all_metrics = {
            'system': system_metrics,
            'database': database_metrics,
            'cache': cache_metrics,
            'application': application_metrics,
            'collected_at': datetime.now().isoformat()
        }
        
        if business_metrics:
            all_metrics['business'] = business_metrics
        
        # 输出到控制台
        self.stdout.write(json.dumps(all_metrics, indent=2, ensure_ascii=False))
        
        # 检查告警
        if options.get('check_alerts'):
            alerts = []
            
            if system_metrics:
                alerts.extend(alert_manager.check_system_alerts(system_metrics))
            
            if application_metrics:
                alerts.extend(alert_manager.check_application_alerts(application_metrics))
            
            if database_metrics:
                alerts.extend(alert_manager.check_database_alerts(database_metrics))
            
            if business_metrics:
                # 这里可以添加业务指标告警检查
                pass
            
            # 发送告警
            for alert in alerts:
                alert_manager.send_alert(alert)
            
            self.stdout.write(f"Generated {len(alerts)} alerts")
        
        # 输出到文件
        if options.get('output_file'):
            with open(options['output_file'], 'w') as f:
                json.dump(all_metrics, f, indent=2, ensure_ascii=False)
            self.stdout.write(f"Metrics saved to {options['output_file']}")


def setup_performance_monitoring():
    """设置性能监控"""
    # 创建监控表（如果需要）
    # 这里可以创建用于存储历史性能数据的数据库表
    
    logger.info("Performance monitoring system initialized")


# 性能监控API视图
def get_system_metrics(request):
    """获取系统指标API"""
    monitor = PerformanceMonitor()
    metrics = monitor.get_system_metrics()
    return JsonResponse(metrics)

def get_database_metrics(request):
    """获取数据库指标API"""
    monitor = PerformanceMonitor()
    metrics = monitor.get_database_metrics()
    return JsonResponse(metrics)

def get_application_metrics(request):
    """获取应用指标API"""
    monitor = PerformanceMonitor()
    metrics = monitor.get_application_metrics()
    return JsonResponse(metrics)

def get_alerts(request):
    """获取告警列表API"""
    hours = request.GET.get('hours', 24)
    alert_manager = AlertManager()
    alerts = alert_manager.get_recent_alerts(int(hours))
    return JsonResponse({'alerts': alerts})


# 业务指标监控
class BusinessMetricsCollector:
    """业务指标收集器"""
    
    def __init__(self):
        self.performance_monitor = PerformanceMonitor()
    
    def get_workorder_metrics(self):
        """获取施工单业务指标"""
        try:
            from workorder.models.core import WorkOrder
            from django.db.models import F
            from datetime import timedelta
            
            # 使用缓存优化数据收集
            cached_metrics = cache.get('workorder_business_metrics')
            if cached_metrics:
                return {
                    'user_metrics': cached_metrics,
                    **cached_workorder_metrics
                }
            
            # 某本统计
            total_workorders = WorkOrder.objects.count()
            pending_workorders = WorkOrder.objects.filter(status='pending').count()
            in_progress_workorders = WorkOrder.objects.filter(status='in_progress').count()
            completed_workorders = WorkOrder.objects.filter(status='completed').count()
            
            # 计算完成率
            completion_rate = (completed_workorders / total_workorders * 100) if total_workorders > 0 else 0
            
            # 最近7天的统计
            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_workorders = WorkOrder.objects.filter(created_at__gte=seven_days_ago).count()
            
            # 平均完成时间（使用简化版本，避免复杂的ORM操作）
            avg_completion_time_hours = 0  # 默认值，避免ORM操作错误
            
            return {
                'total_workorders': total_workorders,
                'pending_workorders': pending_workorders,
                'in_progress_workorders': in_progress_workorders,
                'completed_workorders': completed_workorders,
                'completion_rate': completion_rate,
                'recent_workorders': recent_workorders,
                'avg_completion_time_hours': avg_completion_time_hours,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting workorder metrics: {e}")
            return None
    
    def get_user_activity_metrics(self):
        """获取用户活动指标"""
        try:
            from django.contrib.auth.models import User
            
            # 用户统计
            total_users = User.objects.count()
            active_users = User.objects.filter(is_active=True).count()
            
            # 最近24小时活跃用户
            yesterday = datetime.now() - timedelta(hours=24)
            recent_active_users = User.objects.filter(
                last_login__gte=yesterday
            ).count()
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'recent_active_users': recent_active_users,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting user activity metrics: {e}")
            return None