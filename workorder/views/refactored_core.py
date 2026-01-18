"""
重构后的核心视图

使用业务逻辑服务分离关注点，简化视图逻辑
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..services.api_gateway import (
    WorkOrderAPIService, TaskAPIService, ReportAPIService, SystemAPIService
)
from ..services.business_logic import WorkOrderBusinessService, TaskBusinessService
from ..permissions import SuperuserFriendlyModelPermissions
from ..serializers.core import (
    WorkOrderListSerializer, WorkOrderCreateUpdateSerializer, 
    WorkOrderDetailSerializer, WorkOrderTaskSerializer
)


class RefactoredWorkOrderViewSet(viewsets.ModelViewSet):
    """重构后的施工单视图集"""
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """获取查询集"""
        from ..models.core import WorkOrder
        return WorkOrder.objects.all().select_related(
            'customer', 'created_by', 'approved_by'
        ).prefetch_related(
            'workorderprocess_set__process',
            'workorderproduct_set__product',
            'workordermaterial_set__material',
            'workordertask_set'
        )
    
    def create(self, request, *args, **kwargs):
        """创建施工单"""
        return WorkOrderAPIService.create_workorder(request.data, request.user)
    
    def update(self, request, *args, **kwargs):
        """更新施工单"""
        workorder_id = kwargs.get('pk')
        return WorkOrderAPIService.update_workorder(workorder_id, request.data, request.user)
    
    def list(self, request, *args, **kwargs):
        """获取施工单列表"""
        filters = {
            'page': int(request.query_params.get('page', 1)),
            'page_size': int(request.query_params.get('page_size', 20)),
            'status': request.query_params.get('status'),
            'approval_status': request.query_params.get('approval_status'),
            'priority': request.query_params.get('priority'),
            'customer_id': request.query_params.get('customer_id'),
            'search': request.query_params.get('search'),
        }
        
        # 移除空值
        filters = {k: v for k, v in filters.items() if v is not None and v != ''}
        
        return WorkOrderAPIService.get_workorder_list(filters, request.user)
    
    def retrieve(self, request, *args, **kwargs):
        """获取施工单详情"""
        workorder_id = kwargs.get('pk')
        return WorkOrderAPIService.get_workorder_detail(workorder_id, request.user)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审核通过施工单"""
        return WorkOrderAPIService.approve_workorder(pk, request.data, request.user)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """审核拒绝施工单"""
        return WorkOrderAPIService.reject_workorder(pk, request.data, request.user)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始施工单"""
        try:
            from ..models.core import WorkOrder
            workorder = WorkOrder.objects.get(id=pk)
            
            success = WorkOrderBusinessService.start_workorder(workorder, request.user)
            
            if success:
                return Response({
                    'success': True,
                    'message': '施工单开始成功',
                    'data': {
                        'id': workorder.id,
                        'started_at': workorder.started_at
                    }
                })
            else:
                return Response({
                    'success': False,
                    'message': '施工单开始失败'
                }, status=400)
        except Exception as e:
            return Response({
                'success': False,
                'message': f'开始失败: {str(e)}'
            }, status=500)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取施工单统计"""
        filters = {}
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            filters['start_date'] = start_date
        if end_date:
            filters['end_date'] = end_date
        
        return ReportAPIService.get_workorder_statistics(filters)


class RefactoredTaskViewSet(viewsets.ModelViewSet):
    """重构后的任务视图集"""
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """获取查询集"""
        from ..models.core import WorkOrderTask
        return WorkOrderTask.objects.all().select_related(
            'workorder', 'process', 'assigned_to', 'created_by'
        )
    
    def list(self, request, *args, **kwargs):
        """获取任务列表"""
        # 如果请求的是我的任务
        if request.query_params.get('my_tasks') == 'true':
            return TaskAPIService.get_my_tasks(request.user, request.query_params.dict())
        
        # 否则返回所有任务
        return Response({
            'success': True,
            'data': list(self.get_queryset().values())
        })
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """分配任务"""
        return TaskAPIService.assign_task(pk, request.data, request.user)
    
    @action(detail=True, methods=['post'])
    def start_task(self, request, pk=None):
        """开始任务"""
        return TaskAPIService.start_task(pk, request.user)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成任务"""
        return TaskAPIService.complete_task(pk, request.data, request.user)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取任务统计"""
        filters = {}
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            filters['start_date'] = start_date
        if end_date:
            filters['end_date'] = end_date
        
        return ReportAPIService.get_task_statistics(filters)


class SystemInfoViewSet(viewsets.GenericViewSet):
    """系统信息视图集"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def info(self, request):
        """获取系统信息"""
        return SystemAPIService.get_system_info()
    
    @action(detail=False, methods=['get'])
    def health(self, request):
        """健康检查"""
        return SystemAPIService.health_check()


class DashboardViewSet(viewsets.GenericViewSet):
    """仪表板视图集"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """获取仪表板概览"""
        from ..services.api_gateway import ReportAPIService
        
        # 获取基本统计
        workorder_stats = ReportAPIService.get_workorder_statistics()
        task_stats = ReportAPIService.get_task_statistics()
        
        # 获取我的任务
        my_tasks = TaskAPIService.get_my_tasks(request.user, {'page': 1, 'page_size': 10})
        
        return Response({
            'success': True,
            'data': {
                'workorder_summary': workorder_stats.data.get('data', {}),
                'task_summary': task_stats.data.get('data', {}),
                'my_recent_tasks': my_tasks.data.get('data', {}).get('items', []),
                'notifications': []  # 这里可以集成通知系统
            }
        })
    
    @action(detail=False, methods=['get'])
    def charts(self, request):
        """获取图表数据"""
        from ..services.api_gateway import ReportAPIService
        from datetime import datetime, timedelta
        
        # 最近30天的数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        filters = {
            'start_date': start_date,
            'end_date': end_date
        }
        
        workorder_stats = ReportAPIService.get_workorder_statistics(filters)
        
        # 构建图表数据
        monthly_data = workorder_stats.data.get('data', {}).get('monthly_stats', [])
        
        chart_data = {
            'workorder_trend': [
                {
                    'month': item.get('month'),
                    'count': item.get('count'),
                    'amount': float(item.get('amount') or 0)
                }
                for item in monthly_data
            ],
            'status_distribution': workorder_stats.data.get('data', {}).get('status_distribution', {}),
            'priority_distribution': workorder_stats.data.get('data', {}).get('priority_stats', {}),
            'completion_rate': workorder_stats.data.get('data', {}).get('completion_rate', 0)
        }
        
        return Response({
            'success': True,
            'data': chart_data
        })


# 为了保持向后兼容，提供简化的序列化器类
class SimpleWorkOrderSerializer:
    """简化的施工单序列化器"""
    
    def __init__(self, instance=None, data=None, many=False, context=None):
        self.instance = instance
        self.data = data
        self.many = many
        self.context = context or {}
    
    @property
    def data(self):
        if self.instance is not None:
            if self.many:
                return [self._serialize_item(item) for item in self.instance]
            else:
                return self._serialize_item(self.instance)
        return self.data
    
    def _serialize_item(self, workorder):
        """序列化单个施工单"""
        return {
            'id': workorder.id,
            'order_number': workorder.order_number,
            'customer_name': workorder.customer.name if workorder.customer else '',
            'total_amount': workorder.total_amount,
            'priority': workorder.priority,
            'status': workorder.status,
            'approval_status': workorder.approval_status,
            'created_at': workorder.created_at,
            'deadline': workorder.deadline
        }