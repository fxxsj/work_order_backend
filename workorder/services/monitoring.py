"""
性能监控和业务监控服务

提供API性能监控、业务指标统计、系统健康检查等功能
"""

import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Any
from functools import wraps
from django.db import connection
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.db.models import Count, Avg, Sum, Q, F
from django.db.models.functions import TruncDate

from ..models.core import WorkOrder, WorkOrderTask


MONITORING_CACHE_VERSION_KEY = "monitoring:version"


def monitoring_cache(cache_name):
    """Cache global monitoring results with a versioned, backend-agnostic key."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            version = cache.get(MONITORING_CACHE_VERSION_KEY, 1)
            arguments = repr((args, sorted(kwargs.items())))
            key = f"monitoring:{cache_name}:v{version}:{arguments}"
            cached = cache.get(key)
            if cached is not None:
                return cached

            result = func(*args, **kwargs)
            timeout = getattr(settings, "CACHE_TIMEOUTS", {}).get("SHORT", 60)
            cache.set(key, result, timeout)
            return result

        return wrapper

    return decorator


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.metrics = {}
        self.slow_query_threshold = getattr(
            settings, "SLOW_QUERY_THRESHOLD", 1.0
        )  # 1秒

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
                        self._record_slow_query(
                            metric_name, execution_time, args, kwargs
                        )

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
        if "execution_times" not in self.metrics:
            self.metrics["execution_times"] = []

        self.metrics["execution_times"].append(
            {
                "name": name,
                "execution_time": execution_time,
                "timestamp": timestamp,
            }
        )

        # 保留最近1000条记录
        if len(self.metrics["execution_times"]) > 1000:
            self.metrics["execution_times"] = self.metrics["execution_times"][
                -1000:
            ]

        # 更新缓存
        cache.set(f"perf:{name}:last_execution", execution_time, 300)
        cache.set(
            f"perf:{name}:avg_execution",
            self._get_avg_execution_time(name),
            300,
        )

    def _record_slow_query(
        self, name: str, execution_time: float, args: tuple, kwargs: dict
    ) -> None:
        """记录慢查询"""
        timestamp = timezone.now().isoformat()

        if "slow_queries" not in self.metrics:
            self.metrics["slow_queries"] = []

        self.metrics["slow_queries"].append(
            {
                "name": name,
                "execution_time": execution_time,
                "timestamp": timestamp,
                "args_count": len(args),
                "kwargs_count": len(kwargs),
                "traceback": self._get_traceback(),
            }
        )

        # 保留最近100条慢查询
        if len(self.metrics["slow_queries"]) > 100:
            self.metrics["slow_queries"] = self.metrics["slow_queries"][-100:]

        # 发送告警（如果配置了）
        self._send_performance_alert(name, execution_time)

    def _record_error(
        self, name: str, execution_time: float, error: str
    ) -> None:
        """记录错误"""
        timestamp = timezone.now().isoformat()

        if "errors" not in self.metrics:
            self.metrics["errors"] = []

        self.metrics["errors"].append(
            {
                "name": name,
                "execution_time": execution_time,
                "error": error,
                "timestamp": timestamp,
            }
        )

        # 保留最近100条错误
        if len(self.metrics["errors"]) > 100:
            self.metrics["errors"] = self.metrics["errors"][-100:]

    def _get_avg_execution_time(self, name: str) -> float:
        """获取平均执行时间"""
        times = [
            m["execution_time"]
            for m in self.metrics.get("execution_times", [])
            if m["name"] == name
        ]
        return sum(times) / len(times) if times else 0.0

    def _get_traceback(self) -> str:
        """获取调用栈"""
        import traceback

        return "".join(traceback.format_stack()[-5:-1])

    def _send_performance_alert(
        self, name: str, execution_time: float
    ) -> None:
        """发送性能告警"""
        if not getattr(settings, "PERFORMANCE_ALERTS_ENABLED", False):
            return

        # 这里可以实现邮件、短信等告警方式
        print(f"PERFORMANCE ALERT: {name} took {execution_time:.2f}s")

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        stats = {
            "total_requests": len(self.metrics.get("execution_times", [])),
            "slow_queries": len(self.metrics.get("slow_queries", [])),
            "errors": len(self.metrics.get("errors", [])),
            "avg_response_time": 0.0,
            "slowest_endpoints": [],
            "error_rate": 0.0,
        }

        execution_times = self.metrics.get("execution_times", [])
        if execution_times:
            # 计算平均响应时间
            total_time = sum(m["execution_time"] for m in execution_times)
            stats["avg_response_time"] = total_time / len(execution_times)

            # 最慢的端点
            sorted_times = sorted(
                execution_times,
                key=lambda x: x["execution_time"],
                reverse=True,
            )
            stats["slowest_endpoints"] = sorted_times[:10]

        # 计算错误率
        total_requests = stats["total_requests"]
        total_errors = stats["errors"]
        if total_requests > 0:
            stats["error_rate"] = (total_errors / total_requests) * 100

        return stats


class BusinessMetrics:
    """业务指标监控"""

    @staticmethod
    @monitoring_cache("workorder_metrics")
    def get_workorder_metrics(time_range: str = "24h") -> Dict[str, Any]:
        """获取施工单业务指标"""
        now = timezone.now()

        if time_range == "24h":
            start_time = now - timedelta(hours=24)
        elif time_range == "7d":
            start_time = now - timedelta(days=7)
        elif time_range == "30d":
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(hours=24)

        queryset = WorkOrder.objects.filter(created_at__gte=start_time)

        # 基础指标
        total_orders = queryset.count()
        completed_orders = queryset.filter(status="completed").count()
        pending_orders = queryset.filter(status="pending").count()
        in_progress_orders = queryset.filter(status="in_progress").count()

        # 审核指标
        approved_orders = queryset.filter(approval_status="approved").count()
        rejected_orders = queryset.filter(approval_status="rejected").count()

        # 金额指标
        total_amount = (
            queryset.aggregate(total=Sum("total_amount"))["total"] or 0
        )
        avg_amount = queryset.aggregate(avg=Avg("total_amount"))["avg"] or 0

        # 优先级分布
        priority_stats = (
            queryset.values("priority")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # 时间相关指标
        avg_completion_time = BusinessMetrics._calculate_avg_completion_time(
            queryset
        )

        return {
            "time_range": time_range,
            "period": {
                "start": start_time.isoformat(),
                "end": now.isoformat(),
            },
            "order_stats": {
                "total": total_orders,
                "completed": completed_orders,
                "pending": pending_orders,
                "in_progress": in_progress_orders,
                "completion_rate": (
                    (completed_orders / total_orders * 100)
                    if total_orders > 0
                    else 0
                ),
            },
            "approval_stats": {
                "approved": approved_orders,
                "rejected": rejected_orders,
                "pending": queryset.filter(
                    approval_status="submitted"
                ).count(),
                "approval_rate": (
                    (
                        approved_orders
                        / (approved_orders + rejected_orders)
                        * 100
                    )
                    if (approved_orders + rejected_orders) > 0
                    else 0
                ),
            },
            "amount_stats": {
                "total": float(total_amount),
                "average": float(avg_amount),
            },
            "priority_distribution": list(priority_stats),
            "time_metrics": {
                "avg_completion_days": avg_completion_time,
                "orders_overdue": queryset.filter(
                    delivery_date__lt=now,
                    status__in=["pending", "in_progress"],
                ).count(),
            },
        }

    @staticmethod
    @monitoring_cache("task_metrics")
    def get_task_metrics(time_range: str = "24h") -> Dict[str, Any]:
        """获取任务业务指标"""
        now = timezone.now()

        if time_range == "24h":
            start_time = now - timedelta(hours=24)
        elif time_range == "7d":
            start_time = now - timedelta(days=7)
        else:
            start_time = now - timedelta(hours=24)

        queryset = WorkOrderTask.objects.filter(created_at__gte=start_time)

        # 基础指标
        total_tasks = queryset.count()
        completed_tasks = queryset.filter(status="completed").count()
        pending_tasks = queryset.filter(status="pending").count()
        in_progress_tasks = queryset.filter(status="in_progress").count()

        # 用户指标
        user_stats = (
            queryset.values("assigned_operator__username")
            .annotate(
                total_tasks=Count("id"),
                completed_tasks=Count("id", filter=Q(status="completed")),
                avg_completion_time=Avg(F("updated_at") - F("created_at")),
            )
            .order_by("-total_tasks")[:10]
        )

        # 超时任务（WorkOrderTask 无 deadline 字段，按更新时间超过 24h/7d 的在办任务兜底）
        overdue_tasks = queryset.filter(
            updated_at__lt=now, status__in=["pending", "in_progress"]
        ).count()

        return {
            "time_range": time_range,
            "task_stats": {
                "total": total_tasks,
                "completed": completed_tasks,
                "pending": pending_tasks,
                "in_progress": in_progress_tasks,
                "completion_rate": (
                    (completed_tasks / total_tasks * 100)
                    if total_tasks > 0
                    else 0
                ),
            },
            "user_performance": list(user_stats),
            "time_metrics": {
                "overdue_tasks": overdue_tasks,
                "overdue_rate": (
                    (overdue_tasks / total_tasks * 100)
                    if total_tasks > 0
                    else 0
                ),
            },
        }

    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """获取系统指标"""
        # 数据库连接数
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE state = 'active'"
                )
                db_connections = cursor.fetchone()[0]
        except Exception:
            db_connections = 0

        # 系统资源使用情况
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # 缓存指标
        cache_info = {"redis_available": False, "hits": 0, "misses": 0}

        try:
            # 尝试获取Redis信息（如果使用Redis缓存）
            import redis

            r = redis.Redis(host="localhost", port=6379, db=0)
            info = r.info()
            cache_info.update(
                {
                    "redis_available": True,
                    "used_memory": info["used_memory"],
                    "max_memory": info["maxmemory"],
                    "hits": info.get("keyspace_hits", 0),
                    "misses": info.get("keyspace_misses", 0),
                }
            )
        except Exception:
            pass

        return {
            "timestamp": timezone.now().isoformat(),
            "database": {
                "connections": db_connections,
                "max_connections": getattr(settings, "DATABASES", {})
                .get("default", {})
                .get("CONN_MAX_AGE", 0),
            },
            "system_resources": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used": memory.used,
                "memory_total": memory.total,
                "disk_used": disk.used,
                "disk_total": disk.total,
                "disk_percent": (disk.used / disk.total) * 100,
            },
            "cache": cache_info,
            "django_settings": {
                "debug": settings.DEBUG,
                "allowed_hosts": getattr(settings, "ALLOWED_HOSTS", []),
                "timezone": settings.TIME_ZONE,
            },
        }

    @staticmethod
    def _calculate_avg_completion_time(queryset) -> float:
        """计算平均完成时间"""
        completed_orders = queryset.filter(status="completed").exclude(
            completed_at__isnull=True, created_at__isnull=True
        )

        if not completed_orders.exists():
            return 0.0

        total_days = 0
        for order in completed_orders:
            if order.completed_at and order.created_at:
                days = (
                    order.completed_at.date() - order.created_at.date()
                ).days
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
            "status": "healthy",
            "timestamp": timezone.now().isoformat(),
            "checks": {},
        }

        # 检查数据库连接
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_status["checks"]["database"] = {
                "status": "ok",
                "response_time": 0.1,
            }
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "error",
                "error": str(e),
            }
            health_status["status"] = "unhealthy"

        # 检查缓存
        try:
            cache.set("health_check", "ok", 10)
            cache.get("health_check")
            health_status["checks"]["cache"] = {"status": "ok"}
        except Exception as e:
            health_status["checks"]["cache"] = {
                "status": "error",
                "error": str(e),
            }
            health_status["status"] = "degraded"

        # 检查系统资源
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()

            if cpu_percent > 90 or memory.percent > 90:
                health_status["checks"]["system_resources"] = {
                    "status": "warning",
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                }
                if health_status["status"] == "healthy":
                    health_status["status"] = "degraded"
            else:
                health_status["checks"]["system_resources"] = {
                    "status": "ok",
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                }
        except Exception as e:
            health_status["checks"]["system_resources"] = {
                "status": "error",
                "error": str(e),
            }
            health_status["status"] = "unhealthy"

        return health_status

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """获取仪表板指标"""
        return {
            "performance": self.performance_monitor.get_performance_stats(),
            "business_workorder": self.business_metrics.get_workorder_metrics(
                "24h"
            ),
            "business_task": self.business_metrics.get_task_metrics("24h"),
            "system": self.business_metrics.get_system_metrics(),
            "health": self.health_check(),
        }


class MonitoringStatsService:
    """视图层用到的聚合/统计服务，进一步减少视图中的业务逻辑。"""

    @staticmethod
    def get_execution_time_stats(
        execution_times: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """按端点聚合执行时间统计。"""
        endpoint_stats: Dict[str, Dict[str, Any]] = {}
        for execution in execution_times:
            name = execution["name"]
            if name not in endpoint_stats:
                endpoint_stats[name] = {
                    "count": 0,
                    "total_time": 0.0,
                    "min_time": float("inf"),
                    "max_time": 0.0,
                    "avg_time": 0.0,
                }

            stats = endpoint_stats[name]
            stats["count"] += 1
            stats["total_time"] += execution["execution_time"]
            stats["min_time"] = min(
                stats["min_time"], execution["execution_time"]
            )
            stats["max_time"] = max(
                stats["max_time"], execution["execution_time"]
            )
            stats["avg_time"] = stats["total_time"] / stats["count"]

        endpoint_list = [
            {"endpoint": name, **stats}
            for name, stats in endpoint_stats.items()
        ]
        endpoint_list.sort(key=lambda x: x["avg_time"], reverse=True)
        return endpoint_list

    @staticmethod
    def get_user_performance(days: int = 30) -> List[Dict[str, Any]]:
        """获取最近 N 天的用户绩效指标。"""
        from ..models.core import WorkOrderTask

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        user_stats = (
            WorkOrderTask.objects.filter(
                created_at__gte=start_date, created_at__lte=end_date
            )
            .values("assigned_operator__username")
            .annotate(
                total_tasks=Count("id"),
                completed_tasks=Count("id", filter=Q(status="completed")),
                avg_completion_time=Avg(F("updated_at") - F("created_at")),
            )
            .filter(assigned_operator__is_active=True)
            .order_by("-completed_tasks")[:20]
        )
        return list(user_stats)

    @staticmethod
    @monitoring_cache("productivity_trends")
    def get_productivity_trends(days: int = 7) -> List[Dict[str, Any]]:
        """获取最近 N 天的生产力趋势。"""
        from ..models.core import WorkOrder, WorkOrderTask

        days = max(int(days), 1)
        today = timezone.localdate()
        first_date = today - timedelta(days=days - 1)
        start = timezone.make_aware(
            datetime.combine(first_date, datetime.min.time())
        )
        end = timezone.make_aware(
            datetime.combine(
                today + timedelta(days=1), datetime.min.time()
            )
        )

        def daily_counts(model):
            return {
                row["date"]: row["count"]
                for row in model.objects.filter(
                    status="completed", updated_at__gte=start, updated_at__lt=end
                )
                .annotate(date=TruncDate("updated_at"))
                .values("date")
                .annotate(count=Count("id"))
            }

        order_counts = daily_counts(WorkOrder)
        task_counts = daily_counts(WorkOrderTask)
        return [
            {
                "date": (first_date + timedelta(days=offset)).isoformat(),
                "completed_orders": order_counts.get(
                    first_date + timedelta(days=offset), 0
                ),
                "completed_tasks": task_counts.get(
                    first_date + timedelta(days=offset), 0
                ),
            }
            for offset in range(days)
        ]

    @staticmethod
    def get_quality_metrics(days: int = 30) -> Dict[str, Any]:
        """获取最近 N 天的质量指标。"""
        from ..models.core import WorkOrderTask

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        tasks_with_defects = WorkOrderTask.objects.filter(
            created_at__gte=start_date, quantity_defective__gt=0
        ).aggregate(
            total_tasks=Count("id"),
            total_defects=Sum("quantity_defective"),
            total_completed=Sum("quantity_completed"),
        )

        total_tasks = tasks_with_defects["total_tasks"] or 0
        total_defects = tasks_with_defects["total_defects"] or 0
        total_completed = tasks_with_defects["total_completed"] or 0

        defect_rate = (
            (total_defects / total_completed * 100)
            if total_completed > 0
            else 0
        )

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "defect_stats": {
                "total_tasks_with_defects": total_tasks,
                "total_defects": total_defects,
                "total_completed": total_completed,
                "defect_rate": round(defect_rate, 2),
            },
            "quality_score": round(100 - defect_rate, 2),
        }

    @staticmethod
    @monitoring_cache("operations_dashboard")
    def get_operations_dashboard() -> Dict[str, Any]:
        """运营仪表盘关键指标聚合。"""
        from ..constants.status import MaterialPurchaseStatus
        from ..models.core import WorkOrderMaterial, WorkOrderTask
        from ..models.inventory import DeliveryOrder, ProductStock
        from ..models.materials import PurchaseOrder
        from ..models.sales import SalesOrder
        from ..services.data_consistency_service import DataConsistencyService

        now = timezone.now()

        unassigned_tasks = WorkOrderTask.objects.filter(
            assigned_department__isnull=True,
            status__in=["pending", "in_progress"],
        ).count()

        pending_materials = WorkOrderMaterial.objects.filter(
            purchase_status=MaterialPurchaseStatus.PENDING
        ).count()

        delayed_purchases = PurchaseOrder.objects.filter(
            expected_date__lt=now.date(),
            status__in=["pending", "ordered"],
        ).count()

        pending_quality_check = ProductStock.objects.filter(
            quality_status="pending"
        ).count()

        pending_payment_orders = SalesOrder.objects.filter(
            status="completed",
            payment_status__in=["unpaid", "partial"],
        ).count()

        unassigned_task_list = list(
            WorkOrderTask.objects.filter(
                assigned_department__isnull=True,
                status__in=["pending", "in_progress"],
            ).values("id", "work_content", "status")[:10]
        )

        today_delivery = DeliveryOrder.objects.filter(
            status="pending",
            delivery_date=now.date(),
        ).count()

        overdue_orders = SalesOrder.objects.filter(
            delivery_date__lt=now.date(),
            status__in=["pending", "in_production"],
        ).count()

        inventory_check = DataConsistencyService.check_inventory_consistency()

        return {
            "unassigned_tasks": {
                "count": unassigned_tasks,
                "items": unassigned_task_list,
            },
            "pending_procurement": {
                "materials_count": pending_materials,
                "delayed_purchases": delayed_purchases,
            },
            "quality_and_inventory": {
                "pending_quality_check": pending_quality_check,
                "pending_stock_in": 0,
            },
            "finance": {
                "pending_payment_orders": pending_payment_orders,
            },
            "delivery": {
                "today_delivery": today_delivery,
                "overdue_orders": overdue_orders,
            },
            "inventory_consistency": {
                "status": inventory_check["status"],
                "issue_count": len(inventory_check["issues"]),
            },
            "generated_at": now.isoformat(),
        }

    @staticmethod
    def get_resource_usage() -> Dict[str, Any]:
        """获取系统资源使用情况。"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        try:
            network = psutil.net_io_counters()
            network_stats = {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv,
            }
        except Exception:
            network_stats = {}

        return {
            "timestamp": timezone.now().isoformat(),
            "cpu": {"percent": cpu_percent, "count": psutil.cpu_count()},
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent,
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": (disk.used / disk.total) * 100,
            },
            "network": network_stats,
            "load_average": (
                psutil.getloadavg() if hasattr(psutil, "getloadavg") else []
            ),
        }

    @staticmethod
    def get_alert_settings() -> Dict[str, Any]:
        """获取告警设置。"""
        from django.conf import settings

        return {
            "performance_alerts": {
                "enabled": getattr(
                    settings, "PERFORMANCE_ALERTS_ENABLED", False
                ),
                "slow_query_threshold": getattr(
                    settings, "SLOW_QUERY_THRESHOLD", 1.0
                ),
                "error_rate_threshold": getattr(
                    settings, "ERROR_RATE_THRESHOLD", 5.0
                ),
                "cpu_threshold": getattr(
                    settings, "CPU_ALERT_THRESHOLD", 80.0
                ),
                "memory_threshold": getattr(
                    settings, "MEMORY_ALERT_THRESHOLD", 80.0
                ),
                "disk_threshold": getattr(
                    settings, "DISK_ALERT_THRESHOLD", 80.0
                ),
            },
            "business_alerts": {
                "enabled": getattr(settings, "BUSINESS_ALERTS_ENABLED", False),
                "overdue_orders_threshold": getattr(
                    settings, "OVERDUE_ORDERS_THRESHOLD", 5
                ),
                "defect_rate_threshold": getattr(
                    settings, "DEFECT_RATE_THRESHOLD", 5.0
                ),
                "completion_rate_threshold": getattr(
                    settings, "COMPLETION_RATE_THRESHOLD", 80.0
                ),
            },
            "notification_channels": {
                "email": getattr(settings, "ALERT_EMAIL_ENABLED", True),
                "sms": getattr(settings, "ALERT_SMS_ENABLED", False),
                "webhook": getattr(settings, "ALERT_WEBHOOK_ENABLED", False),
                "webhook_url": getattr(settings, "ALERT_WEBHOOK_URL", ""),
            },
        }

    @staticmethod
    def get_alerts() -> List[Dict[str, Any]]:
        """根据当前系统状态生成告警列表。"""
        alerts = []
        performance_stats = (
            monitoring_service.performance_monitor.get_performance_stats()
        )
        if performance_stats["error_rate"] > 5.0:
            alerts.append(
                {
                    "type": "performance",
                    "level": "warning",
                    "message": (
                        f"系统错误率过高: "
                        f'{performance_stats["error_rate"]:.2f}%'
                    ),
                    "timestamp": timezone.now().isoformat(),
                }
            )

        system_metrics = BusinessMetrics.get_system_metrics()
        resources = system_metrics["system_resources"]

        if resources["cpu_percent"] > 80:
            alerts.append(
                {
                    "type": "resource",
                    "level": "warning",
                    "message": f'CPU使用率过高: {resources["cpu_percent"]:.1f}%',
                    "timestamp": timezone.now().isoformat(),
                }
            )

        if resources["memory_percent"] > 80:
            alerts.append(
                {
                    "type": "resource",
                    "level": "warning",
                    "message": f'内存使用率过高: {resources["memory_percent"]:.1f}%',
                    "timestamp": timezone.now().isoformat(),
                }
            )

        workorder_metrics = BusinessMetrics.get_workorder_metrics("24h")
        overdue_orders = workorder_metrics["time_metrics"]["orders_overdue"]

        if overdue_orders > 5:
            alerts.append(
                {
                    "type": "business",
                    "level": "warning",
                    "message": f"逾期订单过多: {overdue_orders}个",
                    "timestamp": timezone.now().isoformat(),
                }
            )

        return alerts


# 全局监控实例
monitoring_service = MonitoringService()
