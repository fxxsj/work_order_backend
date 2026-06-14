"""
施工单任务统计和导出 Mixin

包含统计查询和导出方法。
"""

import hashlib
import logging
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, F, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.permissions import IsAuthenticated
from workorder.response import APIResponse
from workorder.docs.work_order_tasks_stats import (
    task_assignment_history_docs,
    task_collaboration_stats_docs,
    task_department_workload_docs,
    task_export_docs,
)

from workorder.export_utils import export_tasks
from workorder.models import WorkOrderTask
from workorder.permission_utils import PermissionCache
from workorder.permissions.permission_utils import is_manager_user
from workorder.services.collaboration_stats_service import CollaborationStatsService
from workorder.services.task_log_service import TaskLogService
from workorder.throttling import ExportRateThrottle

logger = logging.getLogger(__name__)


class TaskStatsMixin:
    """
    统计和导出 Mixin

    提供统计查询和导出方法。
    """

    # Cache configuration
    DEPT_WORKLOAD_CACHE_PREFIX = "dept_workload"
    COLLAB_STATS_CACHE_PREFIX = "collab_stats"
    CACHE_TIMEOUT = 300  # 5 minutes

    def _get_collaboration_stats_cache_key(self, start_date, end_date, department_id):
        """Generate cache key for collaboration stats"""
        # Create a hash of parameters for cache key
        params = f"{start_date or ''}:{end_date or ''}:{department_id or ''}"
        params_hash = hashlib.md5(params.encode()).hexdigest()[:8]  # nosec
        return f"{self.COLLAB_STATS_CACHE_PREFIX}:{params_hash}"

    @action(detail=False, methods=["get"], throttle_classes=[ExportRateThrottle])
    @task_export_docs
    def export(self, request):
        """导出任务列表到 Excel（P1 优化：添加速率限制）"""
        # 权限检查：需要查看权限
        if not request.user.has_perm("workorder.view_workorder"):
            return APIResponse.error("您没有权限导出任务数据", code=status.HTTP_403_FORBIDDEN)

        # 获取过滤后的查询集（使用 get_queryset 确保权限过滤）
        queryset = self.filter_queryset(self.get_queryset())

        # 记录导出日志（可选）
        # 这里可以添加导出日志记录功能

        # 导出 Excel
        filename = request.query_params.get("filename")
        return export_tasks(queryset, filename)

    @action(detail=False, methods=["get"], permission_classes=[IsAdminUser])
    @task_assignment_history_docs
    def assignment_history(self, request):
        """分派历史查询：查询任务分派调整历史记录"""
        # 获取查询参数
        task_id = request.query_params.get("task_id")
        department_id = request.query_params.get("department_id")
        operator_id = request.query_params.get("operator_id")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))

        data = TaskLogService.get_assignment_history(
            task_id=task_id,
            department_id=department_id,
            operator_id=operator_id,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
        return APIResponse.success(data=data)

    @action(detail=False, methods=["get"])
    @task_collaboration_stats_docs
    def collaboration_stats(self, request):
        """协作统计：按操作员汇总完成任务数量、完成时间、不良品率等

        Query optimization: Uses annotated queries to eliminate N+1 problem
        Expected queries: <10 total (down from 1+ queries per operator)
        """
        # 获取查询参数
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        department_id = request.query_params.get("department_id")

        data = CollaborationStatsService.get_stats(
            start_date=start_date,
            end_date=end_date,
            department_id=department_id,
        )
        return APIResponse.success(data=data)

    @action(detail=False, methods=["get"])
    @task_department_workload_docs
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
        from django.db.models import Case, Count, F, IntegerField, Q, When

        # 权限检查：只有主管（有 change_workorder 权限的用户）可以访问
        if not request.user.has_perm("workorder.change_workorder"):
            return APIResponse.error("您没有权限查看部门工作负载统计", code=status.HTTP_400_BAD_REQUEST)

        # 获取部门ID参数
        department_id = request.query_params.get("department_id")

        user_department_scope = PermissionCache.get_user_department_scope(request.user)

        # 如果没有指定部门，使用用户所属的第一个部门
        if not department_id:
            user_departments = PermissionCache.get_user_departments(request.user)
            if user_departments:
                department_id = user_departments[0]
            else:
                return APIResponse.error("未指定部门且用户不属于任何部门", code=status.HTTP_400_BAD_REQUEST)

        try:
            department_id = int(department_id)
        except (ValueError, TypeError):
            return APIResponse.error("部门ID格式无效", code=status.HTTP_400_BAD_REQUEST)

        # 获取部门信息
        try:
            from workorder.models.base import Department

            department = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            return APIResponse.error("部门不存在", code=status.HTTP_404_NOT_FOUND)

        if not request.user.is_superuser and not is_manager_user(request.user):
            if department.id not in user_department_scope:
                return APIResponse.error("您没有权限查看该部门工作负载统计", code=status.HTTP_403_FORBIDDEN)

        department_scope = [department.id] + [
            descendant.id for descendant in department.get_descendants()
        ]

        # Check cache first
        cache_key = f"{self.DEPT_WORKLOAD_CACHE_PREFIX}:{department_id}:{','.join(map(str, sorted(department_scope)))}"
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            logger.info(f"Cache HIT for department {department_id} workload")
            return APIResponse.success(data=cached_data)

        logger.info(f"Cache MISS for department {department_id} workload")

        # 获取部门的所有任务（使用 select_related 优化查询）
        tasks = (
            WorkOrderTask.objects.filter(assigned_department_id__in=department_scope)
            .select_related(
                "assigned_operator", "assigned_department", "work_order_process"
            )
            .prefetch_related("logs")
        )

        # Query optimization: Use aggregate for status counts instead of multiple filter().count()
        status_counts = tasks.aggregate(
            total_tasks=Count("id"),
            pending_tasks=Count("id", filter=Q(status="pending")),
            in_progress_tasks=Count("id", filter=Q(status="in_progress")),
            completed_tasks=Count("id", filter=Q(status="completed")),
            cancelled_tasks=Count("id", filter=Q(status="cancelled")),
        )

        total_tasks = status_counts["total_tasks"] or 0
        pending_tasks = status_counts["pending_tasks"] or 0
        in_progress_tasks = status_counts["in_progress_tasks"] or 0
        completed_tasks = status_counts["completed_tasks"] or 0
        cancelled_tasks = status_counts["cancelled_tasks"] or 0

        today = timezone.now().date()
        due_soon_end = today + timedelta(days=2)
        execution_risk = tasks.aggregate(
            overdue_tasks=Count(
                "id",
                filter=Q(
                    work_order_process__work_order__delivery_date__lt=today
                )
                & ~Q(status__in=["completed", "cancelled"]),
            ),
            due_soon_tasks=Count(
                "id",
                filter=Q(
                    work_order_process__work_order__delivery_date__gte=today,
                    work_order_process__work_order__delivery_date__lte=due_soon_end,
                )
                & ~Q(status__in=["completed", "cancelled"]),
            ),
            unassigned_tasks=Count(
                "id",
                filter=Q(assigned_operator__isnull=True)
                & ~Q(status__in=["completed", "cancelled"]),
            ),
            handoff_tasks=Count("id", filter=Q(status="completed")),
        )

        # 计算完成率
        completion_rate = round(
            (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 2
        )

        # 按操作员分组统计
        operators_data = (
            User.objects.filter(
                assigned_tasks__assigned_department_id__in=department_scope, is_active=True
            )
            .exclude(is_superuser=True)
            .annotate(
                operator_id=F("id"),
                operator_name=F("username"),
                pending_count=Count(
                    "assigned_tasks", filter=Q(assigned_tasks__status="pending")
                ),
                in_progress_count=Count(
                    "assigned_tasks", filter=Q(assigned_tasks__status="in_progress")
                ),
                completed_count=Count(
                    "assigned_tasks", filter=Q(assigned_tasks__status="completed")
                ),
                cancelled_count=Count(
                    "assigned_tasks", filter=Q(assigned_tasks__status="cancelled")
                ),
                total_count=Count("assigned_tasks"),
            )
            .values(
                "operator_id",
                "operator_name",
                "pending_count",
                "in_progress_count",
                "completed_count",
                "cancelled_count",
                "total_count",
            )
        )

        # 为每个操作员计算完成率
        operators_list = []
        for op_data in operators_data:
            total = op_data["total_count"]
            completed = op_data["completed_count"]
            op_data["completion_rate"] = round(
                (completed / total * 100) if total > 0 else 0, 2
            )
            operators_list.append(op_data)

        # 按总任务数降序排序
        operators_list.sort(key=lambda x: x["total_count"], reverse=True)

        # Query optimization: Use aggregate for priority distribution instead of multiple filter().count()
        priority_data = tasks.aggregate(
            urgent=Count(
                "id", filter=Q(work_order_process__work_order__priority="urgent")
            ),
            high=Count("id", filter=Q(work_order_process__work_order__priority="high")),
            normal=Count(
                "id", filter=Q(work_order_process__work_order__priority="normal")
            ),
            low=Count("id", filter=Q(work_order_process__work_order__priority="low")),
        )
        priority_distribution = {
            "urgent": priority_data["urgent"] or 0,
            "high": priority_data["high"] or 0,
            "normal": priority_data["normal"] or 0,
            "low": priority_data["low"] or 0,
        }

        # 构建响应
        response_data = {
            "department_id": department.id,
            "department_name": department.name,
            "summary": {
                "total_tasks": total_tasks,
                "pending_tasks": pending_tasks,
                "in_progress_tasks": in_progress_tasks,
                "completed_tasks": completed_tasks,
                "cancelled_tasks": cancelled_tasks,
                "completion_rate": completion_rate,
                "overdue_tasks": execution_risk["overdue_tasks"] or 0,
                "due_soon_tasks": execution_risk["due_soon_tasks"] or 0,
                "unassigned_tasks": execution_risk["unassigned_tasks"] or 0,
                "handoff_tasks": execution_risk["handoff_tasks"] or 0,
            },
            "operators": operators_list,
            "priority_distribution": priority_distribution,
        }

        # Cache the result
        cache.set(cache_key, response_data, self.CACHE_TIMEOUT)
        logger.info(f"Cached department workload data for department {department_id}")

        return APIResponse.success(data=response_data)
