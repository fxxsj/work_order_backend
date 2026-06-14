"""客户订单业务服务

将 SalesOrderViewSet 中的客户订单业务逻辑下沉到服务层，视图只负责入参/出参。
"""

from decimal import Decimal
from typing import Optional

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status

from ..models.sales import SalesOrder
from ..serializers.sales import (
    SalesOrderDetailSerializer,
    SalesOrderListSerializer,
)
from ..services.approval_service import ApprovalService
from ..services.sales_order_status_service import SalesOrderStatusService
from ..services.service_errors import ServiceError


class SalesOrderService:
    """客户订单业务服务"""

    @staticmethod
    def get_summary(queryset):
        """获取客户订单汇总统计。"""
        summary = queryset.aggregate(
            total_count=Count("id"),
            draft_count=Count("id", filter=Q(approval_status="draft")),
            submitted_count=Count("id", filter=Q(approval_status="submitted")),
            approved_count=Count(
                "id", filter=Q(approval_status="approved", status="pending")
            ),
            rejected_count=Count("id", filter=Q(approval_status="rejected")),
            in_production_count=Count("id", filter=Q(status="in_production")),
            completed_count=Count("id", filter=Q(status="completed")),
            cancelled_count=Count("id", filter=Q(status="cancelled")),
        )
        status_stats = (
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )
        return {"summary": summary, "by_status": list(status_stats)}

    @staticmethod
    def submit_for_approval(*, sales_order: SalesOrder, user, auto_approve: bool = False):
        """提交客户订单审核。"""
        if sales_order.approval_status not in ["draft", "rejected"]:
            raise ServiceError(
                "只有草稿或已拒绝状态的订单才能提交",
                code=status.HTTP_400_BAD_REQUEST,
            )

        errors = sales_order.validate_before_approval()
        if errors:
            raise ServiceError(
                "订单数据验证失败",
                code=status.HTTP_400_BAD_REQUEST,
                data={"errors": errors},
            )

        service = ApprovalService(SalesOrder)
        sales_order = service.submit_for_approval(
            sales_order, user, auto_approve=auto_approve
        )
        sales_order.rejection_reason = ""
        sales_order.save(update_fields=["rejection_reason"])
        return sales_order

    @staticmethod
    def approve(*, sales_order: SalesOrder, user, comment: str = ""):
        """审核通过客户订单。"""
        if sales_order.approval_status != "submitted":
            raise ServiceError(
                "只有已提交状态的订单才能审核", code=status.HTTP_400_BAD_REQUEST
            )

        errors = sales_order.validate_before_approval()
        if errors:
            raise ServiceError(
                "订单数据验证失败",
                code=status.HTTP_400_BAD_REQUEST,
                data={"errors": errors},
            )

        service = ApprovalService(SalesOrder)
        sales_order = service.approve(sales_order, user, comment)
        sales_order.completion_reason = ""
        sales_order.save(update_fields=["completion_reason"])
        return sales_order

    @staticmethod
    def reject(*, sales_order: SalesOrder, user, reason: str = "", comment: str = ""):
        """拒绝客户订单。"""
        if sales_order.approval_status != "submitted":
            raise ServiceError(
                "只有已提交状态的订单才能拒绝", code=status.HTTP_400_BAD_REQUEST
            )

        if not reason:
            raise ServiceError(
                "请提供拒绝原因", code=status.HTTP_400_BAD_REQUEST
            )

        service = ApprovalService(SalesOrder)
        sales_order = service.reject(sales_order, user, reason, comment)
        sales_order.rejection_reason = reason
        sales_order.save(update_fields=["rejection_reason"])
        return sales_order

    @staticmethod
    def start_production(*, sales_order: SalesOrder):
        """根据关联施工单同步生产状态。"""
        if (
            sales_order.approval_status != "approved"
            or sales_order.status in ["completed", "cancelled"]
        ):
            raise ServiceError(
                "只有已审核且未完成/取消的订单才能同步生产状态",
                code=status.HTTP_400_BAD_REQUEST,
            )
        if not sales_order.get_related_work_orders_queryset().exists():
            raise ServiceError(
                "请先创建施工单，系统会自动同步为生产中",
                code=status.HTTP_400_BAD_REQUEST,
            )

        SalesOrderStatusService.sync_status(sales_order)
        return sales_order

    @staticmethod
    def complete(*, sales_order: SalesOrder, completion_reason: str = ""):
        """完成客户订单。"""
        if (
            sales_order.approval_status != "approved"
            or sales_order.status in ["completed", "cancelled"]
        ):
            raise ServiceError(
                "只有已审核且未完成/取消的订单才能完成",
                code=status.HTTP_400_BAD_REQUEST,
            )

        all_delivered = SalesOrderStatusService.all_items_delivered(sales_order)
        completion_reason = str(completion_reason).strip()
        if not all_delivered and not completion_reason:
            raise ServiceError(
                "订单未全部发货，人工完结必须填写原因",
                code=status.HTTP_400_BAD_REQUEST,
            )

        sales_order.status = "completed"
        sales_order.completion_reason = "" if all_delivered else completion_reason
        update_fields = ["status", "completion_reason"]
        if all_delivered and sales_order.actual_delivery_date is None:
            sales_order.actual_delivery_date = timezone.now().date()
            update_fields.append("actual_delivery_date")
        sales_order.save(update_fields=update_fields)
        return sales_order

    @staticmethod
    def cancel(*, sales_order: SalesOrder, reason: str = ""):
        """取消客户订单。"""
        if sales_order.status in ["completed", "cancelled"]:
            raise ServiceError(
                "已完成或已取消的订单不能再次取消",
                code=status.HTTP_400_BAD_REQUEST,
            )

        sales_order.status = "cancelled"
        sales_order.rejection_reason = reason
        sales_order.save()
        return sales_order

    @staticmethod
    def update_payment(
        *,
        sales_order: SalesOrder,
        paid_amount: Optional[str] = None,
        payment_date: Optional[str] = None,
    ):
        """更新客户订单付款信息。"""
        if paid_amount is not None:
            if not payment_date:
                raise ServiceError(
                    "更新已付金额时必须提供付款日期",
                    code=status.HTTP_400_BAD_REQUEST,
                )
            sales_order.paid_amount = Decimal(str(paid_amount))
            sales_order.payment_date = payment_date

        sales_order.save()  # save 方法会自动更新 payment_status
        return sales_order
