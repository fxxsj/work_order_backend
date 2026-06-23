"""
财务业务服务

将 finance.py 视图集中的业务逻辑下沉到服务层：
- InvoiceService：发票提交、审核、汇总
- ProductionCostService：生产成本计算与统计
- PaymentPlanService：收款计划汇总
- StatementService：对账单确认、汇总、生成

收款/供应商付款的核心回写逻辑仍保留在 payment_service.py / supplier_payment_service.py，
这里只补充汇总与状态变更方法。
"""

from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Optional

from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from rest_framework import status

from workorder.services.approval_service import ApprovalService
from workorder.services.service_errors import ServiceError

logger = logging.getLogger(__name__)


class InvoiceService:
    """发票服务"""

    @staticmethod
    def submit(invoice, user, auto_approve: bool = False):
        """提交发票。"""
        if invoice.approval_status not in ["draft", "rejected"]:
            raise ServiceError(
                "只有草稿或已拒绝状态的发票可以提交",
                code=status.HTTP_400_BAD_REQUEST,
            )

        from workorder.models import Invoice

        service = ApprovalService(Invoice)
        invoice = service.submit_for_approval(
            invoice, user, auto_approve=auto_approve
        )
        if invoice.status == "draft":
            invoice.status = "issued"
        invoice.save(update_fields=["status"])
        return invoice

    @staticmethod
    def approve(
        invoice,
        user,
        approved: bool = True,
        approval_comment: str = "",
    ):
        """审核发票。"""
        if invoice.approval_status != "submitted":
            raise ServiceError(
                "只有已提交状态的发票可以审核",
                code=status.HTTP_400_BAD_REQUEST,
            )

        from workorder.models import Invoice

        service = ApprovalService(Invoice)
        if approved:
            invoice = service.approve(invoice, user, approval_comment)
            invoice.status = "received"
        else:
            invoice = service.reject(
                invoice, user, approval_comment, approval_comment
            )
            invoice.status = "cancelled"
            if approval_comment:
                invoice.notes = (
                    f"{invoice.notes}\n审核意见: {approval_comment}"
                    if invoice.notes
                    else f"审核意见: {approval_comment}"
                )
        invoice.save(update_fields=["status", "notes"])
        return invoice

    @staticmethod
    def get_summary(queryset) -> dict:
        """发票汇总统计。"""
        actionable_statuses = ["issued", "sent", "received"]
        pending_payment_queryset = queryset.filter(
            status__in=actionable_statuses,
            received_payment_amount__lt=F("total_amount"),
        )

        summary = queryset.aggregate(
            total_count=Count("id"),
            total_amount=Sum("total_amount"),
            tax_amount=Sum("tax_amount"),
            pending_issue_count=Count("id", filter=Q(status="draft")),
            pending_attachment_count=Count(
                "id",
                filter=Q(status__in=actionable_statuses)
                & (Q(attachment="") | Q(attachment__isnull=True)),
            ),
            pending_receipt_count=Count(
                "id", filter=Q(status__in=["issued", "sent"])
            ),
        )

        summary["total_amount"] = summary["total_amount"] or Decimal("0")
        summary["tax_amount"] = summary["tax_amount"] or Decimal("0")
        summary["pending_payment_count"] = pending_payment_queryset.count()

        pending_payment_amount = Decimal("0")
        for (
            _,
            total_amount,
            received_amount,
        ) in pending_payment_queryset.values_list(
            "id", "total_amount", "received_payment_amount"
        ):
            gap = (total_amount or Decimal("0")) - (
                received_amount or Decimal("0")
            )
            if gap > 0:
                pending_payment_amount += gap
        summary["pending_payment_amount"] = pending_payment_amount

        status_stats = (
            queryset.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )

        return {"summary": summary, "by_status": list(status_stats)}


class ProductionCostService:
    """生产成本服务"""

    @staticmethod
    def calculate_material(cost):
        """自动计算材料成本。"""
        try:
            cost.auto_calculate_material_cost()
        except Exception as e:
            raise ServiceError(
                f"计算失败: {e}",
                code=status.HTTP_400_BAD_REQUEST,
            ) from e
        return cost

    @staticmethod
    def calculate_total(cost):
        """计算总成本和差异。"""
        try:
            cost.calculate_total_cost()
        except Exception as e:
            raise ServiceError(
                f"计算失败: {e}",
                code=status.HTTP_400_BAD_REQUEST,
            ) from e
        return cost

    @staticmethod
    def get_stats(queryset, period: Optional[str] = None) -> dict:
        """成本统计。"""
        if period:
            queryset = queryset.filter(period=period)

        stats = queryset.aggregate(
            total_orders=Count("work_order"),
            total_cost=Sum("total_cost"),
            total_material=Sum("material_cost"),
            total_labor=Sum("labor_cost"),
            total_equipment=Sum("equipment_cost"),
            total_overhead=Sum("overhead_cost"),
            total_variance=Sum("variance"),
        )
        return stats


class PaymentPlanService:
    """收款计划服务"""

    @staticmethod
    def get_summary(queryset) -> dict:
        """收款计划汇总。"""
        today = timezone.localdate()
        summary = queryset.aggregate(
            total_count=Count("id"),
            planned_amount=Sum("plan_amount"),
            paid_amount=Sum("paid_amount"),
            pending_count=Count("id", filter=Q(status="pending")),
            partial_count=Count("id", filter=Q(status="partial")),
            completed_count=Count("id", filter=Q(status="completed")),
            overdue_count=Count(
                "id", filter=Q(plan_date__lt=today) & ~Q(status="completed")
            ),
            due_today_count=Count(
                "id", filter=Q(plan_date=today) & ~Q(status="completed")
            ),
        )

        remaining_amount = Decimal("0")
        overdue_amount = Decimal("0")
        for (
            plan_amount,
            paid_amount,
            plan_date,
            plan_status,
        ) in queryset.values_list(
            "plan_amount", "paid_amount", "plan_date", "status"
        ):
            gap = (plan_amount or Decimal("0")) - (paid_amount or Decimal("0"))
            if gap <= 0:
                continue
            remaining_amount += gap
            if plan_status != "completed" and plan_date and plan_date < today:
                overdue_amount += gap

        summary["remaining_amount"] = remaining_amount
        summary["overdue_amount"] = overdue_amount
        by_status = (
            queryset.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )
        return {"summary": summary, "by_status": list(by_status)}


class StatementService:
    """对账单服务"""

    @staticmethod
    def confirm(
        statement,
        user,
        confirmed: bool = True,
        confirmation_notes: Optional[str] = None,
    ):
        """确认对账单。"""
        if statement.status not in ["draft", "sent"]:
            raise ServiceError(
                "只有草稿或已发送状态的对账单可以确认",
                code=status.HTTP_400_BAD_REQUEST,
            )

        statement.confirmed_by = user
        statement.confirmed_at = timezone.now()
        statement.confirmation_notes = confirmation_notes
        statement.status = "confirmed" if confirmed else "disputed"
        statement.save()
        return statement

    @staticmethod
    def get_summary(queryset) -> dict:
        """对账单汇总。"""
        summary = queryset.aggregate(
            total_count=Count("id"),
            pending_confirm_count=Count(
                "id", filter=Q(status__in=["draft", "sent"])
            ),
            disputed_count=Count("id", filter=Q(status="disputed")),
            confirmed_count=Count("id", filter=Q(status="confirmed")),
            total_debit=Sum("total_debit"),
            total_credit=Sum("total_credit"),
            closing_balance=Sum("closing_balance"),
        )
        summary["total_debit"] = summary["total_debit"] or Decimal("0")
        summary["total_credit"] = summary["total_credit"] or Decimal("0")
        summary["closing_balance"] = summary["closing_balance"] or Decimal("0")
        by_status = (
            queryset.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )
        return {"summary": summary, "by_status": list(by_status)}

    @staticmethod
    def generate(
        *,
        customer_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        period: Optional[str] = None,
    ) -> dict:
        """生成客户/供应商对账单预览数据。"""
        if not period:
            raise ServiceError(
                "必须指定对账周期",
                code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            year, month = period.split("-")
            start_date = date(int(year), int(month), 1)
            last_day = monthrange(int(year), int(month))[1]
            end_date = date(int(year), int(month), last_day)
        except Exception as e:
            raise ServiceError(
                "周期格式错误，应为 YYYY-MM",
                code=status.HTTP_400_BAD_REQUEST,
            ) from e

        from workorder.models import Payment, SalesOrder, Statement

        statement_type = None
        opening_balance = 0
        total_debit = 0
        total_credit = 0

        if customer_id:
            statement_type = "customer"

            previous = (
                Statement.objects.filter(
                    statement_type="customer",
                    customer_id=customer_id,
                    period__lt=period,
                )
                .order_by("-period")
                .only("closing_balance")
                .first()
            )
            opening_balance = previous.closing_balance if previous else 0

            orders = (
                SalesOrder.objects.filter(
                    customer_id=customer_id,
                    order_date__gte=start_date,
                    order_date__lte=end_date,
                )
                .exclude(status__in=["draft", "rejected", "cancelled"])
                .only("total_amount")
            )
            total_debit = (
                orders.aggregate(total=Sum("total_amount"))["total"] or 0
            )

            payments = Payment.objects.filter(
                customer_id=customer_id,
                payment_date__gte=start_date,
                payment_date__lte=end_date,
            ).only("amount")
            total_credit = (
                payments.aggregate(total=Sum("amount"))["total"] or 0
            )

        elif supplier_id:
            statement_type = "supplier"

            previous = (
                Statement.objects.filter(
                    statement_type="supplier",
                    supplier_id=supplier_id,
                    period__lt=period,
                )
                .order_by("-period")
                .only("closing_balance")
                .first()
            )
            opening_balance = previous.closing_balance if previous else 0

            from workorder.models import PurchaseOrder

            purchase_orders = (
                PurchaseOrder.objects.filter(
                    supplier_id=supplier_id,
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date,
                )
                .exclude(status="cancelled")
                .only("total_amount")
            )
            total_debit = (
                purchase_orders.aggregate(total=Sum("total_amount"))["total"]
                or 0
            )

            # NOTE: 当前系统未建模“供应商付款”记录，本期贷方暂不计算。
            total_credit = 0
        else:
            raise ServiceError(
                "必须指定客户或供应商",
                code=status.HTTP_400_BAD_REQUEST,
            )

        closing_balance = opening_balance + total_debit - total_credit

        return {
            "statement_type": statement_type,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "opening_balance": opening_balance,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "closing_balance": closing_balance,
        }
