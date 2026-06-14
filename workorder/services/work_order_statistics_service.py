"""
施工单统计和候选订单相关服务

将 WorkOrderViewSet 中的统计和候选订单业务逻辑下沉到服务层，保持 views 仅负责入参/出参。
"""

from __future__ import annotations

import logging
from datetime import timedelta

from collections import defaultdict

from django.db.models import Avg, Count, ExpressionWrapper, F, OuterRef, Q, Subquery, Sum
from django.db.models.fields import DurationField
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status

from ..permissions.permission_utils import is_sales_user
from ..models.core import WorkOrder, WorkOrderProcess, WorkOrderProduct, WorkOrderTask
from ..models.sales import SalesOrder, SalesOrderItem
from .service_errors import ServiceError
from ..views.sales import _scope_sales_orders

logger = logging.getLogger(__name__)


class WorkOrderStatisticsService:
    """施工单统计服务"""

    @staticmethod
    def get_dashboard_stats(queryset, user) -> dict:
        """获取施工单仪表盘统计数据。

        包含：
        - 基础统计（状态、优先级、即将到期、待审核）
        - 任务统计（总数、状态、类型、部门分布）
        - 生产效率分析（工序完成率、平均完成时间、任务完成率、不良品率）
        - 业务分析（客户、产品分布）
        """
        total_count = queryset.count()

        # 状态统计：确保所有状态都有数据，即使数量为0
        status_stats = list(
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )
        all_statuses = ["pending", "in_progress", "paused", "completed", "cancelled"]
        status_dict = {item["status"]: item["count"] for item in status_stats}
        status_statistics = [
            {"status": status, "count": status_dict.get(status, 0)}
            for status in all_statuses
        ]

        # 优先级统计：确保所有优先级都有数据，即使数量为0
        priority_stats = list(
            queryset.values("priority").annotate(count=Count("id")).order_by("priority")
        )
        all_priorities = ["low", "normal", "high", "urgent"]
        priority_dict = {item["priority"]: item["count"] for item in priority_stats}
        priority_statistics = [
            {"priority": priority, "count": priority_dict.get(priority, 0)}
            for priority in all_priorities
        ]

        # 即将到期的订单（7天内）
        upcoming_deadline = queryset.filter(
            delivery_date__lte=timezone.now().date() + timedelta(days=7),
            status__in=["pending", "in_progress"],
        ).count()

        # 未审核施工单数量（仅业务员可见，只统计自己负责的）
        pending_approval_count = 0
        if is_sales_user(user):
            pending_approval_count = queryset.filter(
                approval_status="submitted", customer__salesperson=user
            ).count()

        # 任务总数统计
        all_tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order__in=queryset
        )
        task_total_count = all_tasks.count()

        # 任务状态统计
        task_status_stats = list(
            all_tasks.values("status").annotate(count=Count("id")).order_by("status")
        )
        all_task_statuses = ["pending", "in_progress", "completed", "cancelled"]
        task_status_dict = {item["status"]: item["count"] for item in task_status_stats}
        task_status_statistics = [
            {"status": status, "count": task_status_dict.get(status, 0)}
            for status in all_task_statuses
        ]

        # 任务类型统计
        task_type_stats = list(
            all_tasks.values("task_type")
            .annotate(count=Count("id"))
            .order_by("task_type")
        )
        task_type_statistics = [
            {"task_type": item["task_type"], "count": item["count"]}
            for item in task_type_stats
        ]

        # 按部门统计任务
        task_dept_stats = list(
            all_tasks.filter(assigned_department__isnull=False)
            .values("assigned_department__name")
            .annotate(
                count=Count("id"), completed=Count("id", filter=Q(status="completed"))
            )
            .order_by("-count")
        )
        task_department_statistics = [
            {
                "department": item["assigned_department__name"],
                "total": item["count"],
                "completed": item["completed"],
                "completion_rate": (
                    round(item["completed"] / item["count"] * 100, 2)
                    if item["count"] > 0
                    else 0
                ),
            }
            for item in task_dept_stats
        ]

        # 工序完成率统计
        all_processes = WorkOrderProcess.objects.filter(work_order__in=queryset)
        process_total = all_processes.count()
        process_completed = all_processes.filter(status="completed").count()
        process_completion_rate = (
            round(process_completed / process_total * 100, 2)
            if process_total > 0
            else 0
        )

        # 平均完成时间（已完成工序）
        completed_processes = all_processes.filter(
            status="completed",
            actual_start_time__isnull=False,
            actual_end_time__isnull=False,
        )
        avg_completion_time = None
        if completed_processes.exists():
            result = completed_processes.annotate(
                duration=ExpressionWrapper(
                    F("actual_end_time") - F("actual_start_time"),
                    output_field=DurationField(),
                )
            ).aggregate(avg_duration=Avg("duration"))
            avg_duration = result.get("avg_duration")
            if avg_duration:
                avg_completion_time = round(avg_duration.total_seconds() / 3600, 2)

        # 任务完成率统计
        task_completed = all_tasks.filter(status="completed").count()
        task_completion_rate = (
            round(task_completed / task_total_count * 100, 2)
            if task_total_count > 0
            else 0
        )

        # 不良品率统计（已完成任务）
        completed_tasks = all_tasks.filter(status="completed")
        total_production_quantity = completed_tasks.aggregate(
            total=Sum("production_quantity", default=0)
        )["total"]
        total_defective_quantity = completed_tasks.aggregate(
            total=Sum("quantity_defective", default=0)
        )["total"]
        defective_rate = (
            round(total_defective_quantity / total_production_quantity * 100, 2)
            if total_production_quantity > 0
            else 0
        )

        # 按客户统计
        customer_stats = list(
            queryset.values("customer__name")
            .annotate(
                count=Count("id"), completed=Count("id", filter=Q(status="completed"))
            )
            .order_by("-count")[:10]
        )
        customer_statistics = [
            {
                "customer": item["customer__name"],
                "total": item["count"],
                "completed": item["completed"],
                "completion_rate": (
                    round(item["completed"] / item["count"] * 100, 2)
                    if item["count"] > 0
                    else 0
                ),
            }
            for item in customer_stats
        ]

        # 按产品统计
        product_stats = list(
            WorkOrderProduct.objects.filter(work_order__in=queryset)
            .values("product__name", "product__code")
            .annotate(
                count=Count("work_order", distinct=True), total_quantity=Sum("quantity")
            )
            .order_by("-count")[:10]
        )
        product_statistics = [
            {
                "product_name": item["product__name"],
                "product_code": item["product__code"],
                "order_count": item["count"],
                "total_quantity": item["total_quantity"],
            }
            for item in product_stats
        ]

        return {
            # 基础统计
            "total_count": total_count,
            "status_statistics": status_statistics,
            "priority_statistics": priority_statistics,
            "upcoming_deadline_count": upcoming_deadline,
            "pending_approval_count": pending_approval_count,
            # 任务统计
            "task_statistics": {
                "total_count": task_total_count,
                "status_statistics": task_status_statistics,
                "type_statistics": task_type_statistics,
                "department_statistics": task_department_statistics,
                "completion_rate": task_completion_rate,
            },
            # 生产效率分析
            "efficiency_analysis": {
                "process_completion_rate": process_completion_rate,
                "process_total": process_total,
                "process_completed": process_completed,
                "avg_completion_time_hours": avg_completion_time,
                "task_completion_rate": task_completion_rate,
                "defective_rate": defective_rate,
                "total_production_quantity": total_production_quantity,
                "total_defective_quantity": total_defective_quantity,
            },
            # 业务分析
            "business_analysis": {
                "customer_statistics": customer_statistics,
                "product_statistics": product_statistics,
            },
        }


class SalesOrderCandidateService:
    """销售订单候选服务"""

    @staticmethod
    def get_candidates(exclude_work_order_id, user) -> list:
        """返回可关联到施工单的客户订单候选及其可用产品。

        参数:
            exclude_work_order_id: 要排除的施工单ID（编辑时排除自身）
            user: 当前用户，用于权限过滤

        返回:
            候选订单列表，每个订单包含可用产品明细。
        """
        include_sales_order_id = None
        excluded_work_order_id = None
        if exclude_work_order_id:
            try:
                excluded_work_order_id = int(exclude_work_order_id)
            except (TypeError, ValueError):
                raise ServiceError(
                    "exclude_work_order_id 参数无效",
                    code=status.HTTP_400_BAD_REQUEST,
                )

            existing_work_order = (
                WorkOrder.objects.filter(pk=excluded_work_order_id)
                .only("sales_order_id")
                .first()
            )
            if existing_work_order is not None:
                include_sales_order_id = existing_work_order.sales_order_id

        sales_order_queryset = _scope_sales_orders(
            SalesOrder.objects.select_related("customer"), user
        ).filter(
            Q(status__in=["approved", "in_production"]) | Q(pk=include_sales_order_id)
        )

        sales_order_ids = list(
            sales_order_queryset.order_by("-order_date", "-id").values_list(
                "id", flat=True
            )
        )
        if not sales_order_ids:
            return []

        # 子查询：计算每个 SalesOrderItem 已分配数量（排除当前编辑的施工单）
        allocated_subquery = (
            WorkOrderProduct.objects.filter(sales_order_item_id=OuterRef("pk"))
            .exclude(
                work_order_id=excluded_work_order_id
                if excluded_work_order_id
                else None
            )
            .values("sales_order_item_id")
            .annotate(total=Sum("quantity", default=0))
            .values("total")
        )

        available_items = (
            SalesOrderItem.objects.filter(sales_order_id__in=sales_order_ids)
            .select_related("product")
            .annotate(
                allocated_quantity=Coalesce(Subquery(allocated_subquery), 0),
                remaining_quantity=F("quantity") - F("allocated_quantity"),
            )
            .filter(remaining_quantity__gt=0)
        )

        products_by_sales_order = defaultdict(list)
        for item in available_items:
            products_by_sales_order[item.sales_order_id].append(
                {
                    "sales_order_item_id": item.id,
                    "product_id": item.product_id,
                    "product_name": item.product.name if item.product_id else "",
                    "product_code": item.product.code if item.product_id else "",
                    "quantity": item.quantity,
                    "allocated_quantity": item.allocated_quantity,
                    "remaining_quantity": item.remaining_quantity,
                    "unit": item.unit,
                }
            )

        candidates = []
        for sales_order in sales_order_queryset.filter(
            id__in=set(products_by_sales_order.keys())
            | ({include_sales_order_id} if include_sales_order_id else set())
        ):
            available_products = products_by_sales_order.get(sales_order.id, [])
            if not available_products and sales_order.id != include_sales_order_id:
                continue

            candidates.append(
                {
                    "id": sales_order.id,
                    "order_number": sales_order.order_number,
                    "customer": sales_order.customer_id,
                    "customer_name": sales_order.customer.name,
                    "status": sales_order.status,
                    "status_display": sales_order.get_status_display(),
                    "order_date": sales_order.order_date,
                    "delivery_date": sales_order.delivery_date,
                    "available_products": available_products,
                }
            )

        return candidates
