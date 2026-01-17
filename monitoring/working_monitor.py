"""
简化的性能监控工具
专门为当前系统结构设计，避免复杂的模型依赖问题
"""
import time
import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from functools import wraps

# 配置日志
logger = logging.getLogger(__name__)

class PerformanceMetrics:
    """性能指标收集器"""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.counters = defaultdict(int)
        self.alerts = []
        
    def add_timing(self, name: str, duration: float):
        """添加时间指标"""
        self.metrics[name].append(duration)
        
    def add_counter(self, name: str, value: int = 1):
        """添加计数器"""
        self.counters[name] += value
        
    def get_stats(self, name: str) -> Dict[str, Any]:
        """获取指标统计"""
        if name not in self.metrics:
            return {}
            
        values = self.metrics[name]
        if not values:
            return {}
            
        return {
            'count': len(values),
            'avg': statistics.mean(values),
            'min': min(values),
            'max': max(values),
            'recent': values[-10:],  # 最近10次
            'total': sum(values)
        }
        
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有指标统计"""
        return {name: self.get_stats(name) for name in self.metrics.keys()}

# 全局指标收集器
metrics = PerformanceMetrics()

def monitor_performance(name: Optional[str] = None):
    """性能监控装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            metric_name = name or f"{func.__module__}.{func.__name__}"
            
            try:
                result = func(*args, **kwargs)
                metrics.add_counter(f"{metric_name}_success")
                return result
            except Exception as e:
                metrics.add_counter(f"{metric_name}_error")
                logger.error(f"Error in {metric_name}: {e}")
                raise
            finally:
                duration = time.time() - start_time
                metrics.add_timing(metric_name, duration)
                
                # 检查性能阈值
                if duration > 5.0:  # 超过5秒的请求
                    logger.warning(f"Slow operation detected: {metric_name} took {duration:.2f}s")
                    
        return wrapper
    return decorator

class DatabaseMonitor:
    """数据库监控器"""
    
    def __init__(self):
        self.query_count = 0
        self.slow_queries = []
        self.query_times = deque(maxlen=100)
        
    def record_query(self, duration: float, query_type: str = "unknown"):
        """记录查询"""
        self.query_count += 1
        self.query_times.append(duration)
        
        if duration > 2.0:  # 慢查询阈值
            self.slow_queries.append({
                'duration': duration,
                'type': query_type,
                'timestamp': datetime.now()
            })
            
    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计"""
        return {
            'total_queries': self.query_count,
            'slow_queries': len(self.slow_queries),
            'avg_query_time': statistics.mean(self.query_times) if self.query_times else 0,
            'recent_slow_queries': [
                {
                    'duration': q['duration'],
                    'type': q['type'],
                    'timestamp': q['timestamp'].isoformat()
                }
                for q in sorted(self.slow_queries, key=lambda x: x['timestamp'])[-5:]
            ]
        }

class SystemHealthMonitor:
    """系统健康监控"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.db_monitor = DatabaseMonitor()
        self.last_check = datetime.now()
        
    def check_disk_space(self) -> Dict[str, Any]:
        """检查磁盘空间（简化版本）"""
        return {
            'status': 'ok',  # 简化实现
            'message': 'Disk space check not implemented'
        }
        
    def check_memory_usage(self) -> Dict[str, Any]:
        """检查内存使用（简化版本）"""
        return {
            'status': 'ok',  # 简化实现
            'message': 'Memory check not implemented'
        }
        
    def check_database_health(self) -> Dict[str, Any]:
        """检查数据库健康状态"""
        try:
            # 简单的数据库连接检查
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            stats = self.db_monitor.get_stats()
            return {
                'status': 'healthy' if stats['avg_query_time'] < 1.0 else 'warning',
                'stats': stats
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
            
    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康状态汇总"""
        return {
            'uptime': (datetime.now() - self.start_time).total_seconds(),
            'timestamp': datetime.now().isoformat(),
            'disk': self.check_disk_space(),
            'memory': self.check_memory_usage(),
            'database': self.check_database_health(),
            'performance_metrics': metrics.get_all_stats()
        }

# 全局健康监控器
health_monitor = SystemHealthMonitor()

class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self.alert_rules = [
            {
                'name': 'Slow Query',
                'condition': lambda stats: stats.get('avg_query_time', 0) > 2.0,
                'message': 'Database queries are slow',
                'severity': 'warning'
            },
            {
                'name': 'High Error Rate',
                'condition': lambda health: any(
                    key.endswith('_error') and count > 10 
                    for key, count in metrics.counters.items()
                ),
                'message': 'High error rate detected',
                'severity': 'critical'
            }
        ]
        
    def check_alerts(self) -> List[Dict[str, Any]]:
        """检查告警条件"""
        active_alerts = []
        
        # 获取系统健康状态
        health = health_monitor.get_health_summary()
        
        for rule in self.alert_rules:
            try:
                if rule['condition'](health.get('performance_metrics', {})):
                    active_alerts.append({
                        'name': rule['name'],
                        'message': rule['message'],
                        'severity': rule['severity'],
                        'timestamp': datetime.now().isoformat()
                    })
            except Exception as e:
                logger.error(f"Alert rule check failed: {e}")
                
        return active_alerts

# 全局告警管理器
alert_manager = AlertManager()

# 便捷函数
def get_performance_stats() -> Dict[str, Any]:
    """获取性能统计"""
    return {
        'metrics': metrics.get_all_stats(),
        'health': health_monitor.get_health_summary(),
        'alerts': alert_manager.check_alerts()
    }

def log_slow_operation(operation_name: str, duration: float, details: Dict = None):
    """记录慢操作"""
    if duration > 5.0:
        logger.warning(
            f"Slow operation: {operation_name} took {duration:.2f}s. "
            f"Details: {details or {}}"
        )

# Django 中间件集成
class PerformanceMiddleware:
    """性能监控中间件"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        duration = time.time() - start_time
        path = request.get_full_path()
        
        # 记录请求性能
        metrics.add_timing(f"request_{path}", duration)
        metrics.add_counter(f"requests_total")
        
        # 记录慢请求
        if duration > 3.0:
            logger.warning(f"Slow request: {path} took {duration:.2f}s")
            
        return response

# 管理命令使用示例
def generate_performance_report() -> Dict[str, Any]:
    """生成性能报告"""
    return get_performance_stats()

# 导出主要接口
__all__ = [
    'PerformanceMetrics',
    'DatabaseMonitor', 
    'SystemHealthMonitor',
    'AlertManager',
    'PerformanceMiddleware',
    'monitor_performance',
    'get_performance_stats',
    'log_slow_operation',
    'generate_performance_report',
    'metrics',
    'health_monitor',
    'alert_manager'
]