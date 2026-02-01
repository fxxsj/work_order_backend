"""
施工单任务统计和导出 Mixin

包含统计查询和导出方法。
"""

import logging
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache

from workorder.models import WorkOrderTask
from workorder.throttling import ExportRateThrottle

logger = logging.getLogger(__name__)


class TaskStatsMixin:
    """
    统计和导出 Mixin

    提供统计查询和导出方法。
    """

    # Cache configuration
    DEPT_WORKLOAD_CACHE_PREFIX = 'dept_workload'
    COLLAB_STATS_CACHE_PREFIX = 'collab_stats'
    CACHE_TIMEOUT = 300  # 5 minutes

    def _get_collaboration_stats_cache_key(self, start_date, end_date, department_id):
        """Generate cache key for collaboration stats"""
        import hashlib

        # Create a hash of parameters for cache key
        params = f"{start_date or ''}:{end_date or ''}:{department_id or ''}"
        params_hash = hashlib.md5(params.encode()).hexdigest()[:8]
        return f'{self.COLLAB_STATS_CACHE_PREFIX}:{params_hash}'

    @action(detail=False, methods=['get'], throttle_classes=[ExportRateThrottle])
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

    @action(detail=False, methods=['get'])
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

    @action(detail=False, methods=['get'])
    def collaboration_stats(self, request):
        """协作统计：按操作员汇总完成任务数量、完成时间、不良品率等

        Query optimization: Uses annotated queries to eliminate N+1 problem
        Expected queries: <10 total (down from 1+ queries per operator)
        """
        from django.contrib.auth.models import User
        from django.db.models import Count, Sum, Avg, Q, F, ExpressionWrapper, DurationField
        from datetime import datetime, timedelta
        from collections import defaultdict

        # 获取查询参数
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        department_id = request.query_params.get('department_id')

        # Check cache first
        cache_key = self._get_collaboration_stats_cache_key(start_date, end_date, department_id)
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            logger.info(f"Cache HIT for collaboration stats (key: {cache_key})")
            return Response(cached_data)

        logger.info(f"Cache MISS for collaboration stats (key: {cache_key})")

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

        # Get operators with annotated statistics in a SINGLE query
        # Query optimization: Eliminates N+1 problem by using annotate
        operators_data = User.objects.filter(
            assigned_tasks__isnull=False,
            is_active=True
        ).exclude(
            is_superuser=True
        )

        # Apply department filter if specified
        if department_id:
            operators_data = operators_data.filter(
                profile__departments__id=department_id
            )

        # Annotate all statistics in ONE query
        operators_data = operators_data.annotate(
            operator_id=F('id'),
            operator_username=F('username'),
            total_tasks=Count('assigned_tasks', distinct=True),
            completed_tasks=Count('assigned_tasks', filter=Q(assigned_tasks__status='completed'), distinct=True),
            in_progress_tasks=Count('assigned_tasks', filter=Q(assigned_tasks__status='in_progress'), distinct=True),
            pending_tasks=Count('assigned_tasks', filter=Q(assigned_tasks__status='pending'), distinct=True),
            total_completed_quantity=Sum('assigned_tasks__quantity_completed', filter=Q(assigned_tasks__status='completed')),
            total_defective_quantity=Sum('assigned_tasks__quantity_defective', filter=Q(assigned_tasks__status='completed')),
            total_production_quantity=Sum('assigned_tasks__production_quantity', filter=Q(assigned_tasks__status='completed')),
        ).values(
            'operator_id', 'operator_username',
            'total_tasks', 'completed_tasks', 'in_progress_tasks', 'pending_tasks',
            'total_completed_quantity', 'total_defective_quantity', 'total_production_quantity'
        )

        stats_list = []
        operator_ids = []
        for op_data in operators_data:
            total = op_data['total_tasks'] or 0
            completed = op_data['completed_tasks'] or 0
            completed_qty = op_data['total_completed_quantity'] or 0
            defective_qty = op_data['total_defective_quantity'] or 0

            # Calculate defective rate
            defective_rate = round((defective_qty / completed_qty * 100), 2) if completed_qty > 0 else 0

            # Get completion rate
            completion_rate = round((completed / total * 100), 2) if total > 0 else 0

            operator_ids.append(op_data['operator_id'])
            stats_list.append({
                'operator_id': op_data['operator_id'],
                'operator_username': op_data['operator_username'],
                'operator_name': op_data['operator_username'],  # Can be enhanced with get_full_name()
                'departments': [],  # Departments loaded separately if needed
                'total_tasks': total,
                'completed_tasks': completed,
                'in_progress_tasks': op_data['in_progress_tasks'] or 0,
                'pending_tasks': op_data['pending_tasks'] or 0,
                'total_completed_quantity': completed_qty,
                'total_defective_quantity': defective_qty,
                'total_production_quantity': op_data['total_production_quantity'] or 0,
                'defective_rate': defective_rate,
                'completion_rate': completion_rate,
                'avg_completion_hours': None,  # Will be populated below
            })

        # Average completion times (separate optimized query)
        if operator_ids:
            # Bulk fetch completion times using annotation
            completion_data = WorkOrderTask.objects.filter(
                assigned_operator_id__in=operator_ids,
                status='completed',
                created_at__isnull=False
            ).annotate(
                completion_duration=ExpressionWrapper(
                    F('logs__created_at') - F('created_at'),
                    output_field=DurationField()
                )
            ).filter(
                logs__log_type='complete'
            ).values('assigned_operator_id', 'completion_duration')

            # Group by operator and calculate average
            operator_times = defaultdict(list)
            for item in completion_data:
                if item['completion_duration']:
                    hours = item['completion_duration'].total_seconds() / 3600
                    operator_times[item['assigned_operator_id']].append(hours)

            # Map to stats_list
            for stat in stats_list:
                times = operator_times.get(stat['operator_id'], [])
                stat['avg_completion_hours'] = round(sum(times) / len(times), 2) if times else None

        # Load departments for all operators (optimized with prefetch_related)
        if operator_ids:
            operators_with_depts = User.objects.filter(
                id__in=operator_ids
            ).prefetch_related('profile__departments')

            dept_map = {}
            for op in operators_with_depts:
                if hasattr(op, 'profile'):
                    dept_names = [dept.name for dept in op.profile.departments.all()]
                    dept_map[op.id] = dept_names
                else:
                    dept_map[op.id] = []

            # Map departments to stats
            for stat in stats_list:
                stat['departments'] = dept_map.get(stat['operator_id'], [])

        # Summary statistics in one query
        summary_data = User.objects.filter(
            assigned_tasks__isnull=False,
            is_active=True
        ).exclude(
            is_superuser=True
        ).aggregate(
            total_operators=Count('id', distinct=True),
            total_tasks=Count('assigned_tasks'),
            total_completed_tasks=Count('assigned_tasks', filter=Q(assigned_tasks__status='completed')),
            total_completed_quantity=Sum('assigned_tasks__quantity_completed'),
            total_defective_quantity=Sum('assigned_tasks__quantity_defective'),
        )

        # 按完成数量排序（降序）
        stats_list.sort(key=lambda x: x['total_completed_quantity'], reverse=True)

        # Calculate overall defective rate
        total_completed_qty = summary_data['total_completed_quantity'] or 0
        total_defective_qty = summary_data['total_defective_quantity'] or 0
        overall_defective_rate = round((total_defective_qty / total_completed_qty * 100), 2) if total_completed_qty > 0 else 0

        response_data = {
            'results': stats_list,
            'summary': {
                'total_operators': summary_data['total_operators'],
                'total_tasks': summary_data['total_tasks'] or 0,
                'total_completed_tasks': summary_data['total_completed_tasks'] or 0,
                'total_completed_quantity': total_completed_qty,
                'total_defective_quantity': total_defective_qty,
                'overall_defective_rate': overall_defective_rate
            }
        }

        # Cache the result
        cache.set(cache_key, response_data, self.CACHE_TIMEOUT)
        logger.info(f"Cached collaboration stats (key: {cache_key})")

        return Response(response_data)

    @action(detail=False, methods=['get'])
    def department_workload(self, request):
        """Department workload statistics for supervisor dashboard

        GET /workorder-tasks/department_workload/?department_id=123

        Returns:
        - Department summary (total tasks, completion rate)
        - Operator workloads (task count per operator by status)
        - Task distribution by priority
        - Recent task activity
        """
        from django.contrib.auth.models import User
        from django.db.models import Count, Q, F, Case, When, IntegerField

        # 权限检查：只有主管（有 change_workorder 权限的用户）可以访问
        if not request.user.has_perm('workorder.change_workorder'):
            return Response(
                {'error': '您没有权限查看部门工作负载统计'},
                status=status.HTTP_403_FORBIDDEN
            )

        # 获取部门ID参数
        department_id = request.query_params.get('department_id')

        # 如果没有指定部门，使用用户所属的第一个部门
        if not department_id:
            user_departments = request.user.profile.departments.all() if hasattr(request.user, 'profile') else []
            if user_departments.exists():
                department_id = user_departments.first().id
            else:
                return Response(
                    {'error': '未指定部门且用户不属于任何部门'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            department_id = int(department_id)
        except (ValueError, TypeError):
            return Response(
                {'error': '部门ID格式无效'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取部门信息
        try:
            from workorder.models.base import Department
            department = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            return Response(
                {'error': '部门不存在'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check cache first
        cache_key = f'{self.DEPT_WORKLOAD_CACHE_PREFIX}:{department_id}'
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            logger.info(f"Cache HIT for department {department_id} workload")
            return Response(cached_data)

        logger.info(f"Cache MISS for department {department_id} workload")

        # 获取部门的所有任务（使用 select_related 优化查询）
        tasks = WorkOrderTask.objects.filter(
            assigned_department_id=department_id
        ).select_related(
            'assigned_operator', 'assigned_department', 'work_order_process'
        ).prefetch_related(
            'logs'
        )

        # 统计部门任务总数和各状态数量
        total_tasks = tasks.count()
        pending_tasks = tasks.filter(status='pending').count()
        in_progress_tasks = tasks.filter(status='in_progress').count()
        completed_tasks = tasks.filter(status='completed').count()
        cancelled_tasks = tasks.filter(status='cancelled').count()

        # 计算完成率
        completion_rate = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 2)

        # 按操作员分组统计
        operators_data = User.objects.filter(
            assigned_tasks__assigned_department_id=department_id,
            is_active=True
        ).exclude(
            is_superuser=True
        ).annotate(
            operator_id=F('id'),
            operator_name=F('username'),
            pending_count=Count('assigned_tasks', filter=Q(assigned_tasks__status='pending')),
            in_progress_count=Count('assigned_tasks', filter=Q(assigned_tasks__status='in_progress')),
            completed_count=Count('assigned_tasks', filter=Q(assigned_tasks__status='completed')),
            cancelled_count=Count('assigned_tasks', filter=Q(assigned_tasks__status='cancelled')),
            total_count=Count('assigned_tasks')
        ).values(
            'operator_id', 'operator_name',
            'pending_count', 'in_progress_count', 'completed_count', 'cancelled_count', 'total_count'
        )

        # 为每个操作员计算完成率
        operators_list = []
        for op_data in operators_data:
            total = op_data['total_count']
            completed = op_data['completed_count']
            op_data['completion_rate'] = round((completed / total * 100) if total > 0 else 0, 2)
            operators_list.append(op_data)

        # 按总任务数降序排序
        operators_list.sort(key=lambda x: x['total_count'], reverse=True)

        # 统计优先级分布
        priority_distribution = {
            'urgent': tasks.filter(priority='urgent').count(),
            'high': tasks.filter(priority='high').count(),
            'normal': tasks.filter(priority='normal').count(),
            'low': tasks.filter(priority='low').count()
        }

        # 构建响应
        response_data = {
            'department_id': department.id,
            'department_name': department.name,
            'summary': {
                'total_tasks': total_tasks,
                'pending_tasks': pending_tasks,
                'in_progress_tasks': in_progress_tasks,
                'completed_tasks': completed_tasks,
                'cancelled_tasks': cancelled_tasks,
                'completion_rate': completion_rate
            },
            'operators': operators_list,
            'priority_distribution': priority_distribution
        }

        # Cache the result
        cache.set(cache_key, response_data, self.CACHE_TIMEOUT)
        logger.info(f"Cached department workload data for department {department_id}")

        return Response(response_data)


