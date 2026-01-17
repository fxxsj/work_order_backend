"""
P1 优化: 缓存优化的视图示例
演示如何使用缓存装饰器优化数据库查询性能
"""
from django.core.cache import cache
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

from workorder.models.core import WorkOrder
from workorder.serializers.core import WorkOrderSerializer
from workorder.services.cache_service import cache_result, cache_queryset, CacheManager
from workorder.permissions import IsAuthenticated
from .base import BaseViewSet

import logging

logger = logging.getLogger(__name__)


class OptimizedWorkOrderViewSet(BaseViewSet):
    """
    缓存优化的施工单视图集
    使用多层缓存策略提升性能
    """
    queryset = WorkOrder.objects.all()
    serializer_class = WorkOrderSerializer
    permission_classes = [IsAuthenticated]
    
    @cache_queryset(timeout=300, key_prefix='workorder_list_')  # 5分钟缓存
    def list(self, request, *args, **kwargs):
        """
        获取施工单列表（缓存优化）
        """
        # 使用select_related和prefetch_related优化数据库查询
        queryset = self.get_queryset().select_related(
            'customer', 
            'created_by',
            'approved_by'
        ).prefetch_related(
            'products',
            'processes',
            'materials'
        )
        
        # 应用过滤器
        queryset = self.filter_queryset(queryset)
        
        # 分页处理
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(page)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @cache_result(timeout=600, key_prefix='workorder_detail_')  # 10分钟缓存
    def retrieve(self, request, *args, **kwargs):
        """
        获取施工单详情（缓存优化）
        """
        instance = self.get_object()
        
        # 预加载关联数据
        instance = self.get_queryset().select_related(
            'customer', 
            'created_by',
            'approved_by'
        ).prefetch_related(
            'products',
            'processes__assigned_to',
            'materials',
            'order_processes__process',
            'order_processes__materials'
        ).get(pk=kwargs['pk'])
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """
        创建施工单（自动使相关缓存失效）
        """
        response = super().create(request, *args, **kwargs)
        
        # 使列表缓存失效
        CacheManager.invalidate_workorder_cache(0)  # 0表示使所有施工单缓存失效
        
        # 缓存新创建的对象用于快速访问
        if response.status_code == status.HTTP_201_CREATED:
            workorder_id = response.data.get('id')
            CacheManager.cache_workorder_data(
                workorder_id, 
                'basic_info', 
                response.data,
                timeout=300
            )
        
        return response
    
    def update(self, request, *args, **kwargs):
        """
        更新施工单（自动使缓存失效）
        """
        workorder_id = kwargs.get('pk')
        
        # 使特定施工单缓存失效
        CacheManager.invalidate_workorder_cache(workorder_id)
        
        response = super().update(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_200_OK:
            # 重新缓存更新后的数据
            CacheManager.cache_workorder_data(
                workorder_id,
                'basic_info', 
                response.data,
                timeout=300
            )
        
        return response
    
    def destroy(self, request, *args, **kwargs):
        """
        删除施工单（自动使缓存失效）
        """
        workorder_id = kwargs.get('pk')
        
        # 使特定施工单缓存失效
        CacheManager.invalidate_workorder_cache(workorder_id)
        
        # 使列表缓存失效
        CacheManager.invalidate_cache_pattern('workorder_list_')
        
        response = super().destroy(request, *args, **kwargs)
        
        return response
    
    @method_decorator(cache_page(60 * 15))  # 15分钟页面缓存
    @vary_on_headers('Authorization')  # 根据认证头变化
    def statistics(self, request):
        """
        获取施工单统计信息（页面缓存）
        用于仪表板显示
        """
        try:
            # 使用聚合查询优化性能
            stats = {
                'total_count': self.get_queryset().count(),
                'pending_count': self.get_queryset().filter(status='pending').count(),
                'in_progress_count': self.get_queryset().filter(status='in_progress').count(),
                'completed_count': self.get_queryset().filter(status='completed').count(),
                'cancelled_count': self.get_queryset().filter(status='cancelled').count(),
            }
            
            # 缓存计算结果
            cache_key = 'workorder_statistics'
            cached_stats = cache.get(cache_key)
            
            if cached_stats is None:
                # 如果有缓存，直接使用缓存（由cache_page装饰器处理）
                return Response(stats)
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Error generating workorder statistics: {e}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @cache_result(timeout=1800, key_prefix='user_workorders_')  # 30分钟缓存
    def user_workorders(self, request, *args, **kwargs):
        """
        获取用户相关的施工单（缓存优化）
        """
        user = request.user
        if not user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # 获取用户创建的施工单
        queryset = self.get_queryset().filter(created_by=user)
        
        # 应用分页
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(page)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class CachedDashboardViewSet:
    """
    仪表板专用缓存视图集
    为高频访问的仪表板数据提供优化缓存
    """
    
    @cache_result(timeout=300, key_prefix='dashboard_')
    def get_workorder_stats(self, request):
        """获取施工单统计（缓存30分钟）"""
        try:
            from django.db.models import Count, Q
            
            queryset = WorkOrder.objects.all()
            
            stats = {
                'by_status': {
                    'pending': queryset.filter(status='pending').count(),
                    'in_progress': queryset.filter(status='in_progress').count(),
                    'completed': queryset.filter(status='completed').count(),
                    'cancelled': queryset.filter(status='cancelled').count(),
                    'paused': queryset.filter(status='paused').count(),
                },
                'by_priority': {
                    'low': queryset.filter(priority='low').count(),
                    'normal': queryset.filter(priority='normal').count(),
                    'high': queryset.filter(priority='high').count(),
                    'urgent': queryset.filter(priority='urgent').count(),
                },
                'recent': list(
                    queryset.order_by('-created_at')[:10]
                    .values('id', 'order_number', 'customer_name', 'status', 'created_at')
                ),
                'overdue': queryset.filter(
                    delivery_date__lt=timezone.now(),
                    status__in=['pending', 'in_progress']
                ).count(),
            }
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Error in get_workorder_stats: {e}")
            return Response(
                {'error': 'Failed to fetch statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @cache_result(timeout=600, key_prefix='dashboard_')  # 10分钟缓存
    def get_production_stats(self, request):
        """获取生产统计（缓存10分钟）"""
        try:
            from django.db.models import Sum, Count
            from workorder.models.core import WorkOrderTask
            
            # 生产统计
            total_tasks = WorkOrderTask.objects.count()
            completed_tasks = WorkOrderTask.objects.filter(status='completed').count()
            
            stats = {
                'task_completion_rate': round(
                    (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 2
                ),
                'total_quantity': WorkOrder.objects.aggregate(
                    total=Sum('production_quantity')
                )['total'] or 0,
                'completed_quantity': WorkOrder.objects.filter(
                    processes__status='completed'
                ).aggregate(total=Sum('production_quantity'))['total'] or 0,
                'defective_quantity': WorkOrderTask.objects.aggregate(
                    total=Sum('defective_quantity')
                )['total'] or 0,
            }
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Error in get_production_stats: {e}")
            return Response(
                {'error': 'Failed to fetch production statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )