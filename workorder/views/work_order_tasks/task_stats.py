"""
施工单任务统计和导出 Mixin

包含统计查询和导出方法。
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from workorder.throttling import ExportRateThrottle


class TaskStatsMixin:
    """
    统计和导出 Mixin

    提供统计查询和导出方法。
    """

    @action(detail=False, methods=['get'], throttle_classes=[ExportRateThrottle])
    def export(self, request):
        """导出任务列表"""
    def export(self, request):
        """导出任务列表到 Excel（P1 优化：添加速率限制）"""
        # 权限检查：需要查看权限
        if not request.user.has_perm('workorder.view_workorder'):
            return Response(
                {'error': '您没有权限导出任务数据'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 获取过滤后的查询集（使用 get_queryset 确保权限过滤）
        queryset = self.filter_queryset(self.get_queryset())
        
        # 记录导出日志（可选）
        # 这里可以添加导出日志记录功能
        
        # 导出 Excel
        filename = request.query_params.get('filename')
        return export_tasks(queryset, filename)
    
    def assignment_history(self, request):
        """分派历史查询：查询任务分派调整历史记录"""
        from workorder.models.core import TaskLog
        from django.db.models import Q
        
        # 获取查询参数
        task_id = request.query_params.get('task_id')
        department_id = request.query_params.get('department_id')
        operator_id = request.query_params.get('operator_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # 构建查询条件：筛选包含"调整任务分派"的日志
        query = Q(log_type='status_change', content__contains='调整任务分派')
        
        if task_id:
            query &= Q(task_id=task_id)
        
        if department_id:
            # 通过任务查询部门
            query &= Q(task__assigned_department_id=department_id)
        
        if operator_id:
            # 通过任务或日志操作员查询
            query &= (Q(task__assigned_operator_id=operator_id) | Q(operator_id=operator_id))
        
        if start_date:
            try:
                from datetime import datetime
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                query &= Q(created_at__gte=start_date_obj)
            except ValueError:
                pass
        
        if end_date:
            try:
                from datetime import datetime, timedelta
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query &= Q(created_at__lt=end_date_obj)
            except ValueError:
                pass
        
        # 查询日志
        logs = TaskLog.objects.filter(query).select_related(
            'task', 'task__assigned_department', 'task__assigned_operator',
            'operator', 'task__work_order_process', 'task__work_order_process__work_order'
        ).order_by('-created_at')
        
        # 分页
        total = logs.count()
        start = (page - 1) * page_size
        end = start + page_size
        logs = logs[start:end]
        
        # 序列化结果
        from workorder.serializers.core import TaskLogSerializer
        serializer = TaskLogSerializer()
        
        # 构建响应数据，包含额外信息
        results = []
        for log in logs:
            log_data = serializer.to_representation(log)
            # 添加任务和施工单信息
            if log.task:
                log_data['task_info'] = {
                    'id': log.task.id,
                    'work_content': log.task.work_content,
                    'assigned_department': log.task.assigned_department.name if log.task.assigned_department else None,
                    'assigned_operator': log.task.assigned_operator.username if log.task.assigned_operator else None,
                }
                if log.task.work_order_process and log.task.work_order_process.work_order:
                    wo = log.task.work_order_process.work_order
                    log_data['work_order_info'] = {
                        'id': wo.id,
                        'order_number': wo.order_number,
                        'customer_name': wo.customer.name if wo.customer else None,
                    }
            # 添加操作员名称
            if log.operator:
                log_data['operator_name'] = log.operator.username
            results.append(log_data)
        
        return Response({
            'results': results,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        })
    
    def collaboration_stats(self, request):
        """协作统计：按操作员汇总完成任务数量、完成时间、不良品率等"""
        from django.contrib.auth.models import User
        from django.db.models import Count, Sum, Avg, Q, F
        from datetime import datetime, timedelta
        
        # 获取查询参数
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        department_id = request.query_params.get('department_id')
        
        # 构建时间过滤条件
        time_filter = Q()
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                time_filter &= Q(logs__created_at__gte=start_date_obj)
            except ValueError:
                pass
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                time_filter &= Q(logs__created_at__lt=end_date_obj)
            except ValueError:
                pass
        
        # 构建部门过滤条件
        dept_filter = Q()
        if department_id:
            dept_filter = Q(assigned_department_id=department_id)
        
        # 获取所有有任务的操作员
        operators = User.objects.filter(
            assigned_tasks__isnull=False,
            is_active=True
        ).exclude(
            is_superuser=True
        ).distinct()
        
        if department_id:
            operators = operators.filter(profile__departments__id=department_id).distinct()
        
        stats_list = []
        for operator in operators:
            # 获取该操作员的任务
            task_filter = Q(assigned_operator=operator) & dept_filter
            tasks = WorkOrderTask.objects.filter(task_filter)
            
            # 统计总数
            total_tasks = tasks.count()
            completed_tasks = tasks.filter(status='completed').count()
            in_progress_tasks = tasks.filter(status='in_progress').count()
            pending_tasks = tasks.filter(status='pending').count()
            
            # 统计完成数量和不良品数量（只统计已完成的任务）
            completed_task_data = tasks.filter(
                Q(status='completed') & time_filter
            ).aggregate(
                total_completed_quantity=Sum('quantity_completed', default=0),
                total_defective_quantity=Sum('quantity_defective', default=0),
                total_production_quantity=Sum('production_quantity', default=0)
            )
            
            total_completed_quantity = completed_task_data['total_completed_quantity'] or 0
            total_defective_quantity = completed_task_data['total_defective_quantity'] or 0
            total_production_quantity = completed_task_data['total_production_quantity'] or 0
            
            # 计算不良品率
            defective_rate = 0
            if total_completed_quantity > 0:
                defective_rate = round((total_defective_quantity / total_completed_quantity) * 100, 2)
            
            # 统计平均完成时间（从任务创建到完成的时间）
            avg_completion_hours = None
            completed_tasks_with_times = tasks.filter(
                status='completed',
                created_at__isnull=False
            ).filter(time_filter)
            
            if completed_tasks_with_times.exists():
                # 计算平均完成时间（小时）
                completion_times = []
                for task in completed_tasks_with_times:
                    completion_log = task.logs.filter(log_type='complete').first()
                    if completion_log and task.created_at:
                        duration = completion_log.created_at - task.created_at
                        completion_times.append(duration.total_seconds() / 3600)  # 转换为小时
                
                if completion_times:
                    avg_completion_hours = round(sum(completion_times) / len(completion_times), 2)
            
            # 获取操作员所属部门
            departments = operator.profile.departments.all() if hasattr(operator, 'profile') else []
            dept_names = [dept.name for dept in departments]
            
            stats_list.append({
                'operator_id': operator.id,
                'operator_username': operator.username,
                'operator_name': operator.get_full_name() or operator.username,
                'departments': dept_names,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'in_progress_tasks': in_progress_tasks,
                'pending_tasks': pending_tasks,
                'total_completed_quantity': total_completed_quantity,
                'total_defective_quantity': total_defective_quantity,
                'total_production_quantity': total_production_quantity,
                'defective_rate': defective_rate,
                'avg_completion_hours': avg_completion_hours,
                'completion_rate': round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 2)
            })
        
        # 按完成数量排序（降序）
        stats_list.sort(key=lambda x: x['total_completed_quantity'], reverse=True)
        
        return Response({
            'results': stats_list,
            'summary': {
                'total_operators': len(stats_list),
                'total_tasks': sum(s['total_tasks'] for s in stats_list),
                'total_completed_tasks': sum(s['completed_tasks'] for s in stats_list),
                'total_completed_quantity': sum(s['total_completed_quantity'] for s in stats_list),
                'total_defective_quantity': sum(s['total_defective_quantity'] for s in stats_list),
                'overall_defective_rate': round(
                    (sum(s['total_defective_quantity'] for s in stats_list) / 
                     sum(s['total_completed_quantity'] for s in stats_list) * 100)
                    if sum(s['total_completed_quantity'] for s in stats_list) > 0 else 0, 
                    2
                )
            }
        })


