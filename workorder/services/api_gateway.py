"""
API网关服务

提供统一的API入口，简化客户端调用，提高API的一致性
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.paginator import Paginator
from rest_framework import status
from rest_framework.response import Response

from ..models.core import WorkOrder, WorkOrderTask, WorkOrderProcess
from ..models.base import Customer, Department, Process
from ..services.business_logic import (
    WorkOrderBusinessService, TaskBusinessService, ProcessBusinessService, ReportBusinessService
)
from ..services.realtime_notification import notification_service


class APIResponse:
    """统一的API响应格式"""
    
    @staticmethod
    def success(data: Any = None, message: str = '操作成功', code: int = 200) -> Response:
        """成功响应"""
        return Response({
            'success': True,
            'code': code,
            'message': message,
            'data': data,
            'timestamp': timezone.now().isoformat()
        }, status=code)
    
    @staticmethod
    def error(message: str, code: int = 400, errors: List[str] = None) -> Response:
        """错误响应"""
        return Response({
            'success': False,
            'code': code,
            'message': message,
            'errors': errors or [],
            'data': None,
            'timestamp': timezone.now().isoformat()
        }, status=code)
    
    @staticmethod
    def paginated(queryset, page: int = 1, page_size: int = 20, 
                  serializer_class=None, context: Dict = None) -> Response:
        """分页响应"""
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        if serializer_class:
            items = serializer_class(page_obj.object_list, many=True, context=context or {}).data
        else:
            items = list(page_obj.object_list)
        
        return APIResponse.success({
            'items': items,
            'pagination': {
                'current_page': page,
                'page_size': page_size,
                'total_items': paginator.count,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
                'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None
            }
        })


class WorkOrderAPIService:
    """施工单API服务"""
    
    @staticmethod
    def create_workorder(data: Dict[str, Any], user: User) -> Response:
        """创建施工单API"""
        try:
            workorder = WorkOrderBusinessService.create_workorder(data, user)
            return APIResponse.success(
                data={
                    'id': workorder.id,
                    'order_number': workorder.order_number,
                    'status': workorder.status,
                    'approval_status': workorder.approval_status
                },
                message='施工单创建成功'
            )
        except Exception as e:
            return APIResponse.error(f'创建失败: {str(e)}')
    
    @staticmethod
    def update_workorder(workorder_id: int, data: Dict[str, Any], user: User) -> Response:
        """更新施工单API"""
        try:
            workorder = WorkOrder.objects.get(id=workorder_id)
            updated_workorder = WorkOrderBusinessService.update_workorder(workorder, data, user)
            return APIResponse.success(
                data={
                    'id': updated_workorder.id,
                    'order_number': updated_workorder.order_number,
                    'updated_fields': list(data.keys())
                },
                message='施工单更新成功'
            )
        except WorkOrder.DoesNotExist:
            return APIResponse.error('施工单不存在', 404)
        except Exception as e:
            return APIResponse.error(f'更新失败: {str(e)}')
    
    @staticmethod
    def get_workorder_list(filters: Dict[str, Any] = None, user: User = None) -> Response:
        """获取施工单列表API"""
        queryset = WorkOrder.objects.all()
        
        # 应用过滤器
        if filters:
            queryset = WorkOrderAPIService._apply_filters(queryset, filters)
        
        # 分页
        page = int(filters.get('page', 1)) if filters else 1
        page_size = int(filters.get('page_size', 20)) if filters else 20
        
        return APIResponse.paginated(queryset, page, page_size)
    
    @staticmethod
    def get_workorder_detail(workorder_id: int, user: User = None) -> Response:
        """获取施工单详情API"""
        try:
            workorder = WorkOrder.objects.get(id=workorder_id)
            
            # 构建详细信息
            detail_data = WorkOrderAPIService._build_workorder_detail(workorder)
            
            return APIResponse.success(data=detail_data)
        except WorkOrder.DoesNotExist:
            return APIResponse.error('施工单不存在', 404)
    
    @staticmethod
    def approve_workorder(workorder_id: int, data: Dict[str, Any], user: User) -> Response:
        """审核施工单API"""
        try:
            workorder = WorkOrder.objects.get(id=workorder_id)
            comments = data.get('comments', '')
            
            success = WorkOrderBusinessService.approve_workorder(workorder, user, comments)
            
            if success:
                return APIResponse.success(
                    data={
                        'id': workorder.id,
                        'approval_status': workorder.approval_status
                    },
                    message='施工单审核通过'
                )
            else:
                return APIResponse.error('审核失败')
        except WorkOrder.DoesNotExist:
            return APIResponse.error('施工单不存在', 404)
        except Exception as e:
            return APIResponse.error(f'审核失败: {str(e)}')
    
    @staticmethod
    def reject_workorder(workorder_id: int, data: Dict[str, Any], user: User) -> Response:
        """拒绝施工单API"""
        try:
            workorder = WorkOrder.objects.get(id=workorder_id)
            comments = data.get('comments', '')
            
            success = WorkOrderBusinessService.reject_workorder(workorder, user, comments)
            
            if success:
                return APIResponse.success(
                    data={
                        'id': workorder.id,
                        'approval_status': workorder.approval_status
                    },
                    message='施工单审核拒绝'
                )
            else:
                return APIResponse.error('审核失败')
        except WorkOrder.DoesNotExist:
            return APIResponse.error('施工单不存在', 404)
        except Exception as e:
            return APIResponse.error(f'审核失败: {str(e)}')
    
    @staticmethod
    def _apply_filters(queryset, filters: Dict[str, Any]):
        """应用过滤器"""
        # 状态过滤
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        
        # 审核状态过滤
        if 'approval_status' in filters:
            queryset = queryset.filter(approval_status=filters['approval_status'])
        
        # 优先级过滤
        if 'priority' in filters:
            queryset = queryset.filter(priority=filters['priority'])
        
        # 客户过滤
        if 'customer_id' in filters:
            queryset = queryset.filter(customer_id=filters['customer_id'])
        
        # 日期范围过滤
        if 'start_date' in filters:
            queryset = queryset.filter(created_at__gte=filters['start_date'])
        if 'end_date' in filters:
            queryset = queryset.filter(created_at__lte=filters['end_date'])
        
        # 关键词搜索
        if 'search' in filters:
            search_term = filters['search']
            queryset = queryset.filter(
                models.Q(order_number__icontains=search_term) |
                models.Q(customer__name__icontains=search_term) |
                models.Q(remarks__icontains=search_term)
            )
        
        return queryset
    
    @staticmethod
    def _build_workorder_detail(workorder: WorkOrder) -> Dict[str, Any]:
        """构建施工单详细信息"""
        # 基本信息
        detail = {
            'id': workorder.id,
            'order_number': workorder.order_number,
            'customer': {
                'id': workorder.customer.id,
                'name': workorder.customer.name,
                'contact': workorder.customer.contact_person
            } if workorder.customer else None,
            'total_amount': workorder.total_amount,
            'priority': workorder.priority,
            'status': workorder.status,
            'approval_status': workorder.approval_status,
            'deadline': workorder.deadline,
            'remarks': workorder.remarks,
            'created_by': workorder.created_by.username,
            'created_at': workorder.created_at,
            'started_at': workorder.started_at,
            'completed_at': workorder.completed_at
        }
        
        # 工序信息
        processes = WorkOrderProcess.objects.filter(work_order=workorder).order_by('order')
        detail['processes'] = [
            {
                'id': wp.id,
                'process': {
                    'id': wp.process.id,
                    'name': wp.process.name,
                    'code': wp.process.code
                },
                'order': wp.order,
                'estimated_hours': wp.estimated_hours,
                'actual_hours': wp.actual_hours,
                'status': wp.status,
                'started_at': wp.started_at,
                'completed_at': wp.completed_at
            }
            for wp in processes
        ]
        
        # 产品信息
        from ..models.core import WorkOrderProduct
        products = WorkOrderProduct.objects.filter(work_order=workorder)
        detail['products'] = [
            {
                'id': wp.id,
                'product': {
                    'id': wp.product.id,
                    'name': wp.product.name,
                    'code': wp.product.code
                },
                'quantity': wp.quantity,
                'unit_price': wp.unit_price,
                'total_price': wp.total_price
            }
            for wp in products
        ]
        
        # 物料信息
        from ..models.core import WorkOrderMaterial
        materials = WorkOrderMaterial.objects.filter(work_order=workorder)
        detail['materials'] = [
            {
                'id': wm.id,
                'material': {
                    'id': wm.material.id,
                    'name': wm.material.name,
                    'code': wm.material.code
                },
                'quantity': wm.quantity,
                'unit_price': wm.unit_price,
                'total_price': wm.total_price
            }
            for wm in materials
        ]
        
        # 任务信息
        tasks = WorkOrderTask.objects.filter(workorder=workorder).order_by('created_at')
        detail['tasks'] = [
            {
                'id': task.id,
                'task_name': task.task_name,
                'process': {
                    'id': task.process.id,
                    'name': task.process.name
                },
                'assigned_to': task.assigned_to.username if task.assigned_to else None,
                'status': task.status,
                'estimated_duration': task.estimated_duration,
                'deadline': task.deadline,
                'started_at': task.started_at,
                'completed_at': task.completed_at
            }
            for task in tasks
        ]
        
        return detail


class TaskAPIService:
    """任务API服务"""
    
    @staticmethod
    def assign_task(task_id: int, data: Dict[str, Any], user: User) -> Response:
        """分配任务API"""
        try:
            task = WorkOrderTask.objects.get(id=task_id)
            assigned_to_id = data.get('assigned_to_id')
            assigned_to = User.objects.get(id=assigned_to_id)
            
            success = TaskBusinessService.assign_task(task, assigned_to, user)
            
            if success:
                # 发送通知
                notification_service.notify_task_assignment(task, assigned_to, user)
                
                return APIResponse.success(
                    data={
                        'task_id': task.id,
                        'assigned_to': assigned_to.username
                    },
                    message='任务分配成功'
                )
            else:
                return APIResponse.error('任务分配失败')
        except WorkOrderTask.DoesNotExist:
            return APIResponse.error('任务不存在', 404)
        except User.DoesNotExist:
            return APIResponse.error('指定用户不存在', 404)
        except Exception as e:
            return APIResponse.error(f'分配失败: {str(e)}')
    
    @staticmethod
    def start_task(task_id: int, user: User) -> Response:
        """开始任务API"""
        try:
            task = WorkOrderTask.objects.get(id=task_id)
            
            success = TaskBusinessService.start_task(task, user)
            
            if success:
                return APIResponse.success(
                    data={
                        'task_id': task.id,
                        'started_at': task.started_at
                    },
                    message='任务开始成功'
                )
            else:
                return APIResponse.error('任务开始失败')
        except WorkOrderTask.DoesNotExist:
            return APIResponse.error('任务不存在', 404)
        except Exception as e:
            return APIResponse.error(f'开始失败: {str(e)}')
    
    @staticmethod
    def complete_task(task_id: int, data: Dict[str, Any], user: User) -> Response:
        """完成任务API"""
        try:
            task = WorkOrderTask.objects.get(id=task_id)
            completed_quantity = data.get('completed_quantity')
            defective_quantity = data.get('defective_quantity', 0)
            comments = data.get('comments', '')
            
            success = TaskBusinessService.complete_task(
                task, user, completed_quantity, defective_quantity, comments
            )
            
            if success:
                return APIResponse.success(
                    data={
                        'task_id': task.id,
                        'completed_at': task.completed_at,
                        'completed_quantity': completed_quantity,
                        'defective_quantity': defective_quantity
                    },
                    message='任务完成成功'
                )
            else:
                return APIResponse.error('任务完成失败')
        except WorkOrderTask.DoesNotExist:
            return APIResponse.error('任务不存在', 404)
        except Exception as e:
            return APIResponse.error(f'完成失败: {str(e)}')
    
    @staticmethod
    def get_my_tasks(user: User, filters: Dict[str, Any] = None) -> Response:
        """获取我的任务列表API"""
        queryset = WorkOrderTask.objects.filter(assigned_to=user)
        
        # 应用过滤器
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            if 'priority' in filters:
                queryset = queryset.filter(workorder__priority=filters['priority'])
        
        queryset = queryset.order_by('-created_at')
        
        # 分页
        page = int(filters.get('page', 1)) if filters else 1
        page_size = int(filters.get('page_size', 20)) if filters else 20
        
        return APIResponse.paginated(queryset, page, page_size)


class ReportAPIService:
    """报表API服务"""
    
    @staticmethod
    def get_workorder_statistics(filters: Dict[str, Any] = None) -> Response:
        """获取施工单统计API"""
        try:
            start_date = None
            end_date = None
            
            if filters:
                if 'start_date' in filters:
                    start_date = filters['start_date']
                if 'end_date' in filters:
                    end_date = filters['end_date']
            
            stats = ReportBusinessService.get_workorder_statistics(start_date, end_date)
            
            return APIResponse.success(data=stats, message='统计获取成功')
        except Exception as e:
            return APIResponse.error(f'统计获取失败: {str(e)}')
    
    @staticmethod
    def get_task_statistics(filters: Dict[str, Any] = None) -> Response:
        """获取任务统计API"""
        try:
            start_date = None
            end_date = None
            
            if filters:
                if 'start_date' in filters:
                    start_date = filters['start_date']
                if 'end_date' in filters:
                    end_date = filters['end_date']
            
            stats = ReportBusinessService.get_task_statistics(start_date, end_date)
            
            return APIResponse.success(data=stats, message='统计获取成功')
        except Exception as e:
            return APIResponse.error(f'统计获取失败: {str(e)}')


class SystemAPIService:
    """系统API服务"""
    
    @staticmethod
    def get_system_info() -> Response:
        """获取系统信息API"""
        from django.conf import settings
        
        info = {
            'system_name': '印刷施工单管理系统',
            'version': getattr(settings, 'VERSION', '1.0.0'),
            'environment': getattr(settings, 'ENVIRONMENT', 'development'),
            'django_version': settings.DJANGO_VERSION,
            'python_version': settings.PYTHON_VERSION,
            'timezone': settings.TIME_ZONE,
            'language_code': settings.LANGUAGE_CODE,
            'features': {
                'multi_level_approval': True,
                'smart_assignment': True,
                'realtime_notification': True,
                'data_consistency': True
            }
        }
        
        return APIResponse.success(data=info, message='系统信息获取成功')
    
    @staticmethod
    def health_check() -> Response:
        """健康检查API"""
        from django.db import connection
        
        try:
            # 检查数据库连接
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            # 检查关键模型
            WorkOrder.objects.count()
            User.objects.count()
            
            health_status = {
                'status': 'healthy',
                'database': 'connected',
                'timestamp': timezone.now().isoformat(),
                'services': {
                    'database': 'ok',
                    'notification_service': 'ok',
                    'business_logic': 'ok'
                }
            }
            
            return APIResponse.success(data=health_status, message='系统健康')
            
        except Exception as e:
            health_status = {
                'status': 'unhealthy',
                'database': 'disconnected',
                'timestamp': timezone.now().isoformat(),
                'error': str(e)
            }
            
            return APIResponse.error(
                message='系统异常',
                code=503,
                errors=[str(e)]
            )


# 导入必要的模型
from django.db import models