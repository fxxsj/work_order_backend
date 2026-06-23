"""
收款服务。

处理收款记录创建/更新后回写客户订单付款状态、收款计划和发票关联金额。
确保收款 → 订单付款状态的完整闭环。
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


class PaymentService:
    """收款业务服务，负责收款回写订单/发票/收款计划。"""

    @staticmethod
    def apply_payment(*, payment, user=None):
        """
        收款保存后，同步回写关联的客户订单付款状态。

        流程：
        1. 聚合该订单所有收款记录的 applied_amount 合计
        2. 更新 SalesOrder.paid_amount / payment_status / payment_date
        3. 按 FIFO 分配到收款计划 PaymentPlan
        """
        sales_order = payment.sales_order

        if not sales_order:
            logger.debug(
                f"收款 {payment.payment_number} 未关联客户订单，跳过回写"
            )
            return payment

        with transaction.atomic():
            PaymentService._update_sales_order_payment_status(sales_order)
            PaymentService._distribute_to_plans(sales_order)

        logger.info(
            f"收款 {payment.payment_number} 已回写订单 "
            f"{sales_order.order_number}，付款状态 "
            f"{sales_order.payment_status}"
        )

        return payment

    @staticmethod
    def _update_sales_order_payment_status(sales_order):
        """
        聚合订单所有收款的 applied_amount，更新付款状态。

        状态规则：
        - paid_amount >= total_amount → paid，写入 payment_date
        - paid_amount > 0 → partial
        - paid_amount == 0 → unpaid
        """
        from workorder.models.sales import SalesOrder

        # 使用 select_for_update 锁定订单行，避免并发写入
        sales_order = SalesOrder.objects.select_for_update().get(
            pk=sales_order.pk
        )

        total_paid = sales_order.payments.aggregate(
            total=Sum("applied_amount")
        )["total"] or Decimal("0")

        old_status = sales_order.payment_status

        sales_order.paid_amount = total_paid

        if total_paid >= sales_order.total_amount and total_paid > 0:
            sales_order.payment_status = "paid"
            if not sales_order.payment_date:
                sales_order.payment_date = timezone.now().date()
        elif total_paid > 0:
            sales_order.payment_status = "partial"
            # 从 paid 回退到 partial 时，清空 payment_date
            if old_status == "paid" and sales_order.payment_date:
                sales_order.payment_date = None
        else:
            sales_order.payment_status = "unpaid"
            # 全额归零时清空 payment_date
            if sales_order.payment_date:
                sales_order.payment_date = None

        # 使用 update_fields 避免触发 SalesOrder.save() 的全量计算
        sales_order.save(
            update_fields=["paid_amount", "payment_status", "payment_date"]
        )

    @staticmethod
    def _distribute_to_plans(sales_order):
        """
        按 FIFO（plan_date 升序）将已收金额分配到收款计划。

        每个计划最多分配 plan_amount，剩余金额滚到下一个计划。
        """
        plans = list(
            sales_order.payment_plans.select_for_update().order_by("plan_date")
        )
        if not plans:
            return

        total_payments = sales_order.payments.aggregate(
            total=Sum("applied_amount")
        )["total"] or Decimal("0")

        remaining = total_payments

        for plan in plans:
            if remaining <= 0:
                if plan.paid_amount != Decimal("0"):
                    plan.paid_amount = Decimal("0")
                    plan.update_status()  # 内部调用 save()
                continue

            if remaining >= plan.plan_amount:
                plan.paid_amount = plan.plan_amount
                remaining -= plan.plan_amount
            else:
                plan.paid_amount = remaining
                remaining = Decimal("0")

            plan.update_status()  # 内部调用 save()

    @staticmethod
    def get_summary(queryset) -> dict:
        """收款汇总统计。"""
        summary = queryset.aggregate(
            total_count=Count("id"),
            total_amount=Sum("amount"),
            applied_amount=Sum("applied_amount"),
            remaining_amount=Sum("remaining_amount"),
            missing_invoice_link_count=Count(
                "id",
                filter=Q(invoice__isnull=True) & Q(sales_order__isnull=False),
            ),
        )

        summary["total_amount"] = summary["total_amount"] or Decimal("0")
        summary["applied_amount"] = summary["applied_amount"] or Decimal("0")
        summary["remaining_amount"] = summary["remaining_amount"] or Decimal(
            "0"
        )

        summary["pending_writeoff_count"] = queryset.filter(
            remaining_amount__gt=0
        ).count()
        summary["pending_writeoff_amount"] = queryset.filter(
            remaining_amount__gt=0
        ).aggregate(total=Sum("remaining_amount"))["total"] or Decimal("0")

        method_stats = (
            queryset.values("payment_method")
            .annotate(count=Count("id"), total=Sum("amount"))
            .order_by("payment_method")
        )

        return {"summary": summary, "by_method": list(method_stats)}
