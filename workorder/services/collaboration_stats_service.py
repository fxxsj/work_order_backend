"""
协作统计服务

提供操作员协作统计等业务逻辑，包含缓存、查询构建和结果格式化。
"""

import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import (
    Avg,
    Count,
    DurationField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
)

from workorder.models import WorkOrderTask

logger = logging.getLogger(__name__)


class CollaborationStatsService:
    """协作统计服务"""

    CACHE_PREFIX = "collab_stats"
    CACHE_TIMEOUT = 300  # 5 minutes

    @classmethod
    def _get_cache_key(cls, start_date, end_date, department_id):
        """Generate cache key for collaboration stats"""
        params = f"{start_date or ''}:{end_date or ''}:{department_id or ''}"
        params_hash = hashlib.md5(params.encode()).hexdigest()[:8]  # nosec
        return f"{cls.CACHE_PREFIX}:{params_hash}"

    @classmethod
    def get_stats(cls, start_date=None, end_date=None, department_id=None):
        """
        获取协作统计数据。

        Returns:
            dict: 包含 results 和 summary 的统计结果字典
        """
        cache_key = cls._get_cache_key(start_date, end_date, department_id)
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            logger.info(f"Cache HIT for collaboration stats (key: {cache_key})")
            return cached_data

        logger.info(f"Cache MISS for collaboration stats (key: {cache_key})")

        # 构建时间过滤条件
        time_filter = Q()
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
                time_filter &= Q(logs__created_at__gte=start_date_obj)
            except ValueError:
                pass
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(
                    days=1
                )
                time_filter &= Q(logs__created_at__lt=end_date_obj)
            except ValueError:
                pass

        # Get operators with annotated statistics in a SINGLE query
        operators_data = User.objects.filter(
            assigned_tasks__isnull=False, is_active=True
        ).exclude(is_superuser=True)

        # Apply department filter if specified
        if department_id:
            operators_data = operators_data.filter(
                profile__departments__id=department_id
            )

        # Annotate all statistics in ONE query
        operators_data = operators_data.annotate(
            operator_id=F("id"),
            operator_username=F("username"),
            total_tasks=Count("assigned_tasks", distinct=True),
            completed_tasks=Count(
                "assigned_tasks",
                filter=Q(assigned_tasks__status="completed"),
                distinct=True,
            ),
            in_progress_tasks=Count(
                "assigned_tasks",
                filter=Q(assigned_tasks__status="in_progress"),
                distinct=True,
            ),
            pending_tasks=Count(
                "assigned_tasks",
                filter=Q(assigned_tasks__status="pending"),
                distinct=True,
            ),
            total_completed_quantity=Sum(
                "assigned_tasks__quantity_completed",
                filter=Q(assigned_tasks__status="completed"),
            ),
            total_defective_quantity=Sum(
                "assigned_tasks__quantity_defective",
                filter=Q(assigned_tasks__status="completed"),
            ),
            total_production_quantity=Sum(
                "assigned_tasks__production_quantity",
                filter=Q(assigned_tasks__status="completed"),
            ),
        ).values(
            "operator_id",
            "operator_username",
            "total_tasks",
            "completed_tasks",
            "in_progress_tasks",
            "pending_tasks",
            "total_completed_quantity",
            "total_defective_quantity",
            "total_production_quantity",
        )

        stats_list = []
        operator_ids = []
        for op_data in operators_data:
            total = op_data["total_tasks"] or 0
            completed = op_data["completed_tasks"] or 0
            completed_qty = op_data["total_completed_quantity"] or 0
            defective_qty = op_data["total_defective_quantity"] or 0

            # Calculate defective rate
            defective_rate = (
                round((defective_qty / completed_qty * 100), 2)
                if completed_qty > 0
                else 0
            )

            # Get completion rate
            completion_rate = round((completed / total * 100), 2) if total > 0 else 0

            operator_ids.append(op_data["operator_id"])
            stats_list.append(
                {
                    "operator_id": op_data["operator_id"],
                    "operator_username": op_data["operator_username"],
                    "operator_name": op_data["operator_username"],
                    "departments": [],  # Departments loaded separately if needed
                    "total_tasks": total,
                    "completed_tasks": completed,
                    "in_progress_tasks": op_data["in_progress_tasks"] or 0,
                    "pending_tasks": op_data["pending_tasks"] or 0,
                    "total_completed_quantity": completed_qty,
                    "total_defective_quantity": defective_qty,
                    "total_production_quantity": op_data["total_production_quantity"]
                    or 0,
                    "defective_rate": defective_rate,
                    "completion_rate": completion_rate,
                    "avg_completion_hours": None,  # Will be populated below
                }
            )

        # Average completion times (separate optimized query)
        if operator_ids:
            # Bulk fetch completion times using annotation
            completion_data = (
                WorkOrderTask.objects.filter(
                    assigned_operator_id__in=operator_ids,
                    status="completed",
                    created_at__isnull=False,
                )
                .annotate(
                    completion_duration=ExpressionWrapper(
                        F("logs__created_at") - F("created_at"),
                        output_field=DurationField(),
                    )
                )
                .filter(logs__log_type="complete")
                .values("assigned_operator_id", "completion_duration")
            )

            # Group by operator and calculate average
            operator_times = defaultdict(list)
            for item in completion_data:
                if item["completion_duration"]:
                    hours = item["completion_duration"].total_seconds() / 3600
                    operator_times[item["assigned_operator_id"]].append(hours)

            # Map to stats_list
            for stat in stats_list:
                times = operator_times.get(stat["operator_id"], [])
                stat["avg_completion_hours"] = (
                    round(sum(times) / len(times), 2) if times else None
                )

        # Load departments for all operators (optimized with prefetch_related)
        if operator_ids:
            operators_with_depts = User.objects.filter(
                id__in=operator_ids
            ).prefetch_related("profile__departments")

            dept_map = {}
            for op in operators_with_depts:
                if hasattr(op, "profile"):
                    dept_names = [dept.name for dept in op.profile.departments.all()]
                    dept_map[op.id] = dept_names
                else:
                    dept_map[op.id] = []

            # Map departments to stats
            for stat in stats_list:
                stat["departments"] = dept_map.get(stat["operator_id"], [])

        # Summary statistics in one query
        summary_data = (
            User.objects.filter(assigned_tasks__isnull=False, is_active=True)
            .exclude(is_superuser=True)
            .aggregate(
                total_operators=Count("id", distinct=True),
                total_tasks=Count("assigned_tasks"),
                total_completed_tasks=Count(
                    "assigned_tasks", filter=Q(assigned_tasks__status="completed")
                ),
                total_completed_quantity=Sum("assigned_tasks__quantity_completed"),
                total_defective_quantity=Sum("assigned_tasks__quantity_defective"),
            )
        )

        # 按完成数量排序（降序）
        stats_list.sort(key=lambda x: x["total_completed_quantity"], reverse=True)

        # Calculate overall defective rate
        total_completed_qty = summary_data["total_completed_quantity"] or 0
        total_defective_qty = summary_data["total_defective_quantity"] or 0
        overall_defective_rate = (
            round((total_defective_qty / total_completed_qty * 100), 2)
            if total_completed_qty > 0
            else 0
        )

        response_data = {
            "results": stats_list,
            "summary": {
                "total_operators": summary_data["total_operators"],
                "total_tasks": summary_data["total_tasks"] or 0,
                "total_completed_tasks": summary_data["total_completed_tasks"] or 0,
                "total_completed_quantity": total_completed_qty,
                "total_defective_quantity": total_defective_qty,
                "overall_defective_rate": overall_defective_rate,
            },
        }

        # Cache the result
        cache.set(cache_key, response_data, cls.CACHE_TIMEOUT)
        logger.info(f"Cached collaboration stats (key: {cache_key})")

        return response_data
