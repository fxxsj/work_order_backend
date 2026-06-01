"""客户订单状态同步服务。"""

from __future__ import annotations

from collections.abc import Iterable

from django.utils import timezone

from workorder.constants.status import SalesOrderStatus, WorkOrderStatus
from ..models.sales import SalesOrder


class SalesOrderStatusService:
    """根据施工单和发货进度同步客户订单状态。"""

    TERMINAL_STATUSES = {SalesOrderStatus.CANCELLED}
    WORKFLOW_STATUSES = {SalesOrderStatus.APPROVED, SalesOrderStatus.IN_PRODUCTION, SalesOrderStatus.COMPLETED}
    UNFINISHED_WORK_ORDER_STATUSES = {WorkOrderStatus.PENDING, WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.PAUSED}

    @staticmethod
    def get_work_orders_queryset(sales_order: SalesOrder):
        """获取与客户订单关联的施工单。"""
        return sales_order.get_related_work_orders_queryset()

    @staticmethod
    def get_sales_orders_for_work_order(work_order) -> list[SalesOrder]:
        """获取与施工单关联的客户订单。"""
        return work_order.get_related_sales_orders()

    @staticmethod
    def all_items_delivered(sales_order: SalesOrder) -> bool:
        """是否全部发货完成。"""
        items = list(sales_order.items.all())
        if not items:
            return False
        return all(item.is_fully_delivered for item in items)

    @staticmethod
    def has_unfinished_work_orders(sales_order: SalesOrder) -> bool:
        """是否存在未完成的关联施工单。"""
        return SalesOrderStatusService.get_work_orders_queryset(sales_order).filter(
            status__in=SalesOrderStatusService.UNFINISHED_WORK_ORDER_STATUSES
        ).exists()

    @staticmethod
    def sync_status_for_work_order(work_order) -> list[str]:
        """同步某个施工单关联的所有客户订单状态。"""
        statuses = []
        for sales_order in SalesOrderStatusService.get_sales_orders_for_work_order(
            work_order
        ):
            statuses.append(SalesOrderStatusService.sync_status(sales_order))
        return statuses

    @staticmethod
    def sync_status_for_sales_orders(sales_orders: Iterable[SalesOrder]) -> list[str]:
        """批量同步客户订单状态。"""
        statuses = []
        for sales_order in sales_orders:
            statuses.append(SalesOrderStatusService.sync_status(sales_order))
        return statuses

    @staticmethod
    def sync_status(
        sales_order: SalesOrder,
        *,
        preserve_manual_completion: bool = True,
    ) -> str:
        """同步客户订单状态。"""
        current_status = sales_order.status
        if current_status in SalesOrderStatusService.TERMINAL_STATUSES:
            return current_status

        if current_status not in SalesOrderStatusService.WORKFLOW_STATUSES:
            return current_status

        all_delivered = SalesOrderStatusService.all_items_delivered(sales_order)
        unfinished_work_orders = SalesOrderStatusService.has_unfinished_work_orders(
            sales_order
        )

        update_fields = []
        next_status = current_status

        if all_delivered:
            next_status = SalesOrderStatus.COMPLETED
            if sales_order.actual_delivery_date is None:
                sales_order.actual_delivery_date = timezone.now().date()
                update_fields.append("actual_delivery_date")
            if not preserve_manual_completion and sales_order.completion_reason:
                sales_order.completion_reason = ""
                update_fields.append("completion_reason")
        elif (
            preserve_manual_completion
            and current_status == SalesOrderStatus.COMPLETED
            and sales_order.completion_reason.strip()
        ):
            next_status = SalesOrderStatus.COMPLETED
        elif unfinished_work_orders:
            next_status = SalesOrderStatus.IN_PRODUCTION
            if sales_order.actual_delivery_date is not None:
                sales_order.actual_delivery_date = None
                update_fields.append("actual_delivery_date")
        else:
            next_status = SalesOrderStatus.APPROVED
            if sales_order.actual_delivery_date is not None:
                sales_order.actual_delivery_date = None
                update_fields.append("actual_delivery_date")

        if sales_order.status != next_status:
            sales_order.status = next_status
            update_fields.append("status")

        if update_fields:
            sales_order.save(update_fields=update_fields)

        return sales_order.status
