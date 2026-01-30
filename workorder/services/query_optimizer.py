"""
查询优化服务

解决N+1查询问题，提供高效的数据库查询方法：
1. 优化select_related和prefetch_related的使用
2. 实现查询缓存机制
3. 提供批量查询方法
4. 添加查询性能监控
"""

from django.db import models
from django.db.models import Prefetch, Q, Count, Sum, Avg, Max, Min
from django.core.cache import cache
from django.conf import settings
from typing import List, Dict, Any, Optional, Union
import logging
import time

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """查询优化器"""
    
    @staticmethod
    def optimize_workorder_queryset(queryset=None, include_details=False):
        """
        优化施工单查询，解决N+1问题
        
        Args:
            queryset: 基础查询集
            include_details: 是否包含详细信息
        
        Returns:
            优化后的查询集
        """
        from ..models.core import WorkOrder
        
        if queryset is None:
            queryset = WorkOrder.objects.all()
        
        # 基础select_related优化
        queryset = queryset.select_related(
            'customer',
            'customer__salesperson',
            'manager', 
            'created_by',
            'approved_by'
        )
        
        if include_details:
            # 详细信息需要更复杂的prefetch_related
            queryset = queryset.prefetch_related(
                # 产品信息
                Prefetch(
                    'products',
                    queryset=WorkOrder.products.through.objects.select_related('product').order_by('sort_order'),
                    to_attr='ordered_products'
                ),
                
                # 工序信息（包含任务）
                Prefetch(
                    'order_processes',
                    queryset=WorkOrder.order_processes.through.objects.select_related(
                        'process',
                        'department',
                        'operator'
                    ).prefetch_related(
                        Prefetch(
                            'tasks',
                            queryset=WorkOrder.order_processes.through.tasks.through.objects.select_related(
                                'assigned_operator',
                                'assigned_department',
                                'product',
                                'material',
                                'artwork',
                                'die',
                                'foiling_plate',
                                'embossing_plate'
                            ),
                            to_attr='ordered_tasks'
                        )
                    ).order_by('sequence'),
                    to_attr='ordered_processes'
                ),
                
                # 资产信息
                Prefetch('artworks', to_attr='ordered_artworks'),
                Prefetch('dies', to_attr='ordered_dies'),
                Prefetch('foiling_plates', to_attr='ordered_foiling_plates'),
                Prefetch('embossing_plates', to_attr='ordered_embossing_plates'),
                
                # 物料信息
                Prefetch(
                    'materials',
                    queryset=WorkOrder.materials.through.objects.select_related('material'),
                    to_attr='ordered_materials'
                )
            )
        
        return queryset
    
    @staticmethod
    def optimize_task_queryset(queryset=None, include_work_order=False):
        """
        优化任务查询
        
        Args:
            queryset: 基础查询集
            include_work_order: 是否包含施工单信息
        
        Returns:
            优化后的查询集
        """
        from ..models.core import WorkOrderTask
        
        if queryset is None:
            queryset = WorkOrderTask.objects.all()
        
        # 基础select_related优化
        queryset = queryset.select_related(
            'work_order_process',
            'work_order_process__work_order',
            'work_order_process__process',
            'assigned_operator',
            'assigned_department',
            'product',
            'material',
            'artwork',
            'die',
            'foiling_plate',
            'embossing_plate'
        )
        
        if include_work_order:
            # 包含施工单的基础信息
            queryset = queryset.select_related(
                'work_order_process__work_order__customer'
            )
        
        return queryset
    
    @staticmethod
    def batch_get_workorders_with_stats(order_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """
        批量获取施工单及其统计信息
        
        Args:
            order_ids: 施工单ID列表
        
        Returns:
            {order_id: stats_dict}
        """
        from ..models.core import WorkOrder, WorkOrderProcess, WorkOrderTask
        
        # 使用子查询获取统计信息，避免多次查询
        work_orders = WorkOrder.objects.filter(id__in=order_ids).select_related(
            'customer',
            'manager'
        ).annotate(
            # 产品数量统计
            total_products=Count('products', distinct=True),
            
            # 工序统计
            total_processes=Count('order_processes', distinct=True),
            completed_processes=Count(
                'order_processes',
                filter=Q(order_processes__status='completed'),
                distinct=True
            ),
            
            # 任务统计
            total_tasks=Count('order_processes__tasks', distinct=True),
            completed_tasks=Count(
                'order_processes__tasks',
                filter=Q(order_processes__tasks__status='completed'),
                distinct=True
            ),
            
            # 不良品统计
            total_defective=Sum('order_processes__tasks__quantity_defective'),
            
            # 完成数量统计
            total_completed=Sum('order_processes__tasks__quantity_completed')
        )
        
        result = {}
        for work_order in work_orders:
            result[work_order.id] = {
                'work_order': work_order,
                'total_products': work_order.total_products or 0,
                'total_processes': work_order.total_processes or 0,
                'completed_processes': work_order.completed_processes or 0,
                'total_tasks': work_order.total_tasks or 0,
                'completed_tasks': work_order.completed_tasks or 0,
                'total_defective': work_order.total_defective or 0,
                'total_completed': work_order.total_completed or 0,
                'progress_percentage': int(
                    (work_order.completed_processes / work_order.total_processes * 100) 
                    if work_order.total_processes > 0 else 0
                )
            }
        
        return result


class QueryCache:
    """查询缓存管理器"""
    
    CACHE_TIMEOUT = getattr(settings, 'QUERY_CACHE_TIMEOUT', 300)  # 5分钟
    
    @classmethod
    def get_cached_queryset(cls, cache_key: str, queryset_func, timeout: int = None):
        """
        获取缓存的查询结果
        
        Args:
            cache_key: 缓存键
            queryset_func: 查询函数
            timeout: 缓存超时时间
        
        Returns:
            查询结果
        """
        if timeout is None:
            timeout = cls.CACHE_TIMEOUT
        
        result = cache.get(cache_key)
        if result is not None:
            return result
        
        # 执行查询并缓存结果
        result = queryset_func()
        cache.set(cache_key, result, timeout)
        return result
    
    @classmethod
    def invalidate_cache(cls, pattern: str):
        """
        根据模式失效缓存
        
        Args:
            pattern: 缓存键模式
        """
        # 这里需要根据具体缓存后端实现
        # 对于Redis，可以使用通配符删除
        # 对于默认缓存，需要维护一个缓存键列表
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            # 默认缓存不支持模式删除，使用键列表
            keys = cache.keys(pattern)
            if keys:
                cache.delete_many(keys)
    
    @classmethod
    def get_workorder_cache_key(cls, order_id: int, suffix: str = '') -> str:
        """生成施工单缓存键"""
        return f'workorder:{order_id}:{suffix}' if suffix else f'workorder:{order_id}'
    
    @classmethod
    def get_task_cache_key(cls, task_id: int, suffix: str = '') -> str:
        """生成任务缓存键"""
        return f'task:{task_id}:{suffix}' if suffix else f'task:{task_id}'


class QueryPerformanceMonitor:
    """查询性能监控器"""
    
    def __init__(self):
        self.query_times = {}
        self.query_counts = {}
    
    def start_timing(self, query_name: str):
        """开始计时"""
        self.query_times[query_name] = time.time()
    
    def end_timing(self, query_name: str):
        """结束计时"""
        if query_name in self.query_times:
            duration = time.time() - self.query_times[query_name]
            
            if query_name not in self.query_counts:
                self.query_counts[query_name] = {
                    'total_time': 0,
                    'count': 0,
                    'max_time': 0,
                    'min_time': float('inf')
                }
            
            stats = self.query_counts[query_name]
            stats['total_time'] += duration
            stats['count'] += 1
            stats['max_time'] = max(stats['max_time'], duration)
            stats['min_time'] = min(stats['min_time'], duration)
            
            # 记录慢查询
            if duration > 1.0:  # 超过1秒的查询
                logger.warning(f"Slow query detected: {query_name} took {duration:.2f}s")
            
            del self.query_times[query_name]
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """获取性能统计"""
        result = {}
        for query_name, stats in self.query_counts.items():
            avg_time = stats['total_time'] / stats['count']
            result[query_name] = {
                'count': stats['count'],
                'total_time': round(stats['total_time'], 3),
                'avg_time': round(avg_time, 3),
                'max_time': round(stats['max_time'], 3),
                'min_time': round(stats['min_time'], 3) if stats['min_time'] != float('inf') else 0
            }
        return result
    
    def log_stats(self):
        """记录性能统计到日志"""
        stats = self.get_stats()
        for query_name, data in stats.items():
            logger.info(
                f"Query Performance - {query_name}: "
                f"count={data['count']}, "
                f"avg_time={data['avg_time']}s, "
                f"max_time={data['max_time']}s"
            )


# 全局查询监控器实例
query_monitor = QueryPerformanceMonitor()


class PerformanceOptimizedManager(models.Manager):
    """性能优化的模型管理器"""
    
    def get_optimized_queryset(self, include_details=False):
        """获取优化查询集"""
        if hasattr(self.model, '_get_optimized_queryset'):
            return self.model._get_optimized_queryset(super().get_queryset(), include_details)
        return super().get_queryset()
    
    def get_cached(self, cache_key: str, timeout: int = None):
        """获取缓存结果"""
        def queryset_func():
            return list(self.get_optimized_queryset(include_details=True))
        
        return QueryCache.get_cached_queryset(cache_key, queryset_func, timeout)
    
    def batch_update(self, objs: List, fields: List[str]) -> int:
        """批量更新"""
        return self.bulk_update(objs, fields)
    
    def batch_create(self, objs: List) -> List:
        """批量创建"""
        return self.bulk_create(objs)


class WorkOrderOptimizedManager(PerformanceOptimizedManager):
    """施工单优化管理器"""
    
    def get_optimized_queryset(self, queryset, include_details=False):
        """获取优化的施工单查询集"""
        return QueryOptimizer.optimize_workorder_queryset(queryset, include_details)
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """获取仪表板统计信息（优化版）"""
        from ..models.core import WorkOrder
        
        # 使用单个查询获取所有统计信息
        stats = WorkOrder.objects.aggregate(
            total_orders=Count('id'),
            pending_orders=Count('id', filter=Q(status='pending')),
            in_progress_orders=Count('id', filter=Q(status='in_progress')),
            completed_orders=Count('id', filter=Q(status='completed')),
            urgent_orders=Count('id', filter=Q(priority='urgent')),
            pending_approval=Count('id', filter=Q(approval_status='pending'))
        )
        
        # 获取即将到期的订单
        from django.utils import timezone
        upcoming_deadline = timezone.now() + timezone.timedelta(days=3)
        upcoming_deadline_orders = WorkOrder.objects.filter(
            delivery_date__lte=upcoming_deadline,
            status__in=['pending', 'in_progress']
        ).count()
        
        stats['upcoming_deadline_orders'] = upcoming_deadline_orders
        
        return stats
    
    def get_with_progress(self, order_ids: List[int] = None):
        """获取带进度信息的施工单"""
        if order_ids:
            queryset = self.filter(id__in=order_ids)
        else:
            queryset = self.get_optimized_queryset(include_details=True)
        
        # 预计算进度百分比
        return queryset.annotate(
            total_processes=Count('order_processes'),
            completed_processes=Count(
                'order_processes', 
                filter=Q(order_processes__status='completed')
            )
        ).annotate(
            progress_percentage=models.Case(
                models.When(
                    total_processes__gt=0,
                    then=models.F('completed_processes') * 100.0 / models.F('total_processes')
                ),
                default=0,
                output_field=models.FloatField()
            )
        )


class TaskOptimizedManager(PerformanceOptimizedManager):
    """任务优化管理器"""

    def get_optimized_queryset(self, queryset, include_details=False):
        """获取优化的任务查询集"""
        return QueryOptimizer.optimize_task_queryset(queryset, include_details)

    def operational(self):
        """
        获取操作性任务（排除草稿任务）

        Returns:
            QuerySet: 排除了草稿状态的任务查询集
        """
        return self.get_queryset().exclude(status='draft')

    def get_user_task_stats(self, user_id: int) -> Dict[str, int]:
        """获取用户任务统计"""
        from ..models.core import WorkOrderTask

        return WorkOrderTask.objects.filter(
            assigned_operator_id=user_id
        ).aggregate(
            total_tasks=Count('id'),
            pending_tasks=Count('id', filter=Q(status='pending')),
            in_progress_tasks=Count('id', filter=Q(status='in_progress')),
            completed_tasks=Count('id', filter=Q(status='completed')),
            overdue_tasks=Count(
                'id',
                filter=Q(
                    status__in=['pending', 'in_progress'],
                    work_order_process__work_order__delivery_date__lt=timezone.now()
                )
            )
        )


def with_query_monitoring(query_name: str):
    """查询性能监控装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            query_monitor.start_timing(query_name)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                query_monitor.end_timing(query_name)
        return wrapper
    return decorator