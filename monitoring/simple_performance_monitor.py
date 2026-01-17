"""
简化的性能监控脚本
避免复杂的导入和模型访问问题
"""
import json
import logging
import time
import psutil
from datetime import datetime

logger = logging.getLogger(__name__)


def get_system_metrics():
    """获取系统性能指标（简化版本）"""
    try:
        # 系统指标
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 数据库连接检查（简化）
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 as active_connections FROM pg_stat_activity WHERE state = 'active'")
                db_connections = cursor.fetchone()[0]
        except:
            db_connections = 0
        
        return {
            'cpu_percent': cpu_percent,
            'memory': {
                'total': memory.total if memory else 0,
                'used': memory.used if memory else 0,
                'percent': memory.percent if memory else 0
            },
            'disk': {
                'total': disk.total if disk else 0,
                'used': disk.used if disk else 0,
                'free': disk.free if disk else 0,
                'percent': (disk.used / disk.total * 100) if disk.total > 0 else 0
            },
            'network_connections': len(psutil.net_connections()),
            'active_connections': db_connections,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return None


def get_business_metrics():
    """获取业务指标（简化版本）"""
    try:
        # 施工单统计
        from django.db import connection
            
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_workorders,
                    COUNT(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_workorders,
                    COUNT(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_workorders,
                    COUNT(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_workorders
                FROM workorder_workorder 
                """)
            workorder_data = cursor.fetchone()
            
        if workorder_data:
            total_workorders, pending_workorders, in_progress_workorders, completed_workorders = workorder_data
            completion_rate = (completed_workorders / total_workorders * 100) if total_workorders > 0 else 0
            
            # 最近7天统计
            seven_days_ago = datetime.now() - timedelta(days=7)
            cursor.execute("""
                SELECT COUNT(*) as recent_workorders
                FROM workorder_workorder 
                WHERE created_at >= %s
                """, [seven_days_ago.isoformat()])
            recent_workorders = cursor.fetchone()[0]
            
            return {
                'total_workorders': total_workorders,
                'pending_workorders': pending_workorders,
                'in_progress_workorders': in_progress_workorders,
                'completed_workorders': completed_workorders,
                'completion_rate': completion_rate,
                'recent_workorders': recent_workorders,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting workorder metrics: {e}")
            return None


def get_cache_metrics():
    """获取缓存指标（简化版本）"""
    try:
        info = cache.get('cache_info') if cache else None
        if not info:
            return None
            
        return {
            'used_memory': info.get('used_memory_human', '0'),
            'connected_clients': info.get('connected_clients', 0),
            'total_commands_processed': info.get('total_commands_processed', 0),
            'keyspace_hits': info.get('keyspace_hits', 0),
            'keyspace_misses': info.get('keyspace_misses', 0),
            'hit_rate': 0,  # 简化逻辑
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting cache metrics: {e}")
        return None


def get_alert_count():
    """获取告警数量（使用缓存）"""
    try:
        alerts_key = f"alerts_{datetime.now().strftime('%Y%m%d')}"
        all_alerts = cache.get(alerts_key, [])
        return len(all_alerts) if all_alerts else 0
    except Exception as e:
        logger.error(f"Error getting alert count: {e}")
        return 0


def collect_all_metrics():
    """收集所有性能指标"""
    system_metrics = get_system_metrics()
    cache_metrics = get_cache_metrics()
    business_metrics = get_business_metrics()
    alert_count = get_alert_count()
    
    all_metrics = {
        'system': system_metrics,
        'cache': cache_metrics,
        'business': business_metrics,
        'alert_count': alert_count,
        'timestamp': datetime.now().isoformat()
    }
    
    return all_metrics


class AlertChecker:
    """告警检查器"""
    
    def __init__(self, thresholds=None):
        self.thresholds = thresholds or {
            'cpu': 80,  # CPU使用率超过80%
            'memory': 85,  # 内存使用率超过85%
            'disk': 90,  # 磁盘使用率超过90%
            'error_rate': 5,  # 错误率超过5%
            'response_time': 2000, # 响应时间超过2秒
        }
    
    def check_alerts(self, metrics):
        """检查告警条件"""
        alerts = []
        
        # 检查系统指标
        if metrics and metrics.get('cpu_percent', 0) > self.thresholds['cpu']:
            alerts.append({
                'type': 'system',
                'level': 'warning',
                'message': f"CPU使用率过高: {metrics['cpu_percent']}%",
                'timestamp': datetime.now().isoformat()
            })
        
        # 检查内存使用率
        if metrics and metrics.get('memory', {}).get('percent', 0) > self.thresholds['memory']:
            alerts.append({
                'type': 'system',
                'level': 'warning',
                'message': f"内存使用率过高: {metrics['memory']['percent']}%",
                'timestamp': datetime.now().isoformat()
            })
        
        # 检查磁盘使用率
        if metrics and metrics.get('disk', {}).get('percent', 0) > self.thresholds['disk']:
            alerts.append({
                'type': 'system',
                'level': 'critical',
                'message': f"磁盘使用率过高: {metrics['disk']['percent']}%",
                'timestamp': datetime.now().isoformat()
            })
        
        return alerts
    
    def generate_alert_message(self, alert):
        """生成告警消息"""
        if alert['level'] == 'critical':
            return f"🚨️ 系统严重告警：{alert['message']}"
        elif alert['level'] == 'error':
            return f"⚠️ 系统错误：{alert['message']}"
        else:
            return f"⚠️ 系统警告：{alert['message']}"
        
        return f"🔔 系统信息：{alert['message']}"


def save_metrics_to_cache(metrics):
    """保存指标到缓存"""
    try:
        cache.set('all_metrics', metrics, timeout=300)  # 5分钟缓存
        return True
    except Exception as e:
        logger.error(f"Error saving metrics to cache: {e}")
        return False


def setup_monitoring():
    """设置监控"""
    logger.info("Performance monitoring initialized")
    logger.info(f"Alert thresholds: {AlertChecker().thresholds}")


if __name__ == '__main__':
    # 测试监控功能
    print("Testing performance monitor...")
    
    # 获取当前指标
    metrics = collect_all_metrics()
    print(json.dumps(metrics, indent=2))
    
    # 检查告警
    checker = AlertChecker()
    alerts = checker.check_alerts(metrics)
    if alerts:
        for alert in alerts:
            print(AlertChecker().generate_alert_message(alert))
    
    # 测试缓存功能
    cache.set('test_key', 'test_value', timeout=60)
    print("Cache test completed")
    
    # 测试告警检查
    metrics = {
        'cpu_percent': 85,
        'memory': {'percent': 87, 'used': 654321472, 'total': 750593808},
        'disk': {'percent': 45, 'used': 3377543680, 'total': 750593808},
        'error_rate': 2.5
    }
    }
    
    alerts = checker.check_alerts(metrics)
    print("Alert test completed")
    for alert in alerts:
        print(f"Alert: {AlertChecker().generate_alert_message(alert)}")


if __name__ == '__main__':
    setup_monitoring()