"""
供应商付款服务。

处理供应商付款记录创建/更新后回写采购单付款状态，
确保付款 → 采购单付款状态的完整闭环。
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status

from .service_errors import ServiceError

logger = logging.getLogger(__name__)


from workorder.models.system import ApprovalConfig


class SupplierPaymentService:
    """供应商付款业务服务，负责付款回写采购单付款状态。"""

    @staticmethod
    def apply_payment(*, payment, user=None):
        """
        付款保存后，同步回写关联的采购单付款状态。

        流程：
        1. 聚合该采购单所有付款记录的 applied_amount 合计
        2. 更新 PurchaseOrder.paid_amount / payment_status
        """
        purchase_order = payment.purchase_order

        if not purchase_order:
            logger.debug(
                f"付款 {payment.payment_number} 未关联采购单，跳过回写"
            )
            return payment

        with transaction.atomic():
            SupplierPaymentService._update_purchase_order_payment_status(
                purchase_order
            )

        logger.info(
            f"付款 {payment.payment_number} 已回写采购单 "
            f"{purchase_order.order_number}，付款状态 "
            f"{purchase_order.payment_status}"
        )

        return payment

    @staticmethod
    def _update_purchase_order_payment_status(purchase_order):
        """
        聚合采购单所有付款的 applied_amount，更新付款状态。

        状态规则：
        - paid_amount >= total_amount → paid
        - paid_amount > 0 → partial
        - paid_amount == 0 → unpaid
        """
        from workorder.models.materials import PurchaseOrder

        purchase_order = PurchaseOrder.objects.select_for_update().get(
            pk=purchase_order.pk
        )

        total_paid = purchase_order.supplier_payments.filter(
            status="approved"
        ).aggregate(total=Sum("applied_amount"))["total"] or Decimal("0")

        purchase_order.paid_amount = total_paid

        if total_paid >= purchase_order.total_amount and total_paid > 0:
            purchase_order.payment_status = "paid"
        elif total_paid > 0:
            purchase_order.payment_status = "partial"
        else:
            purchase_order.payment_status = "unpaid"

        purchase_order.save(update_fields=["paid_amount", "payment_status"])

    @staticmethod
    def submit(payment, user):
        """提交供应商付款审核。"""
        if payment.status != "pending":
            raise ServiceError(
                "只有待审核状态才能提交",
                code=status.HTTP_400_BAD_REQUEST,
            )
        payment.submitted_by = user
        payment.submitted_at = timezone.now()
        payment.save(update_fields=["submitted_by", "submitted_at"])

        # 模块审核开关：若供应商付款审核已关闭，系统自动通过
        if not ApprovalConfig.get_solo().is_enabled("supplierpayment"):
            return SupplierPaymentService.approve(
                payment=payment,
                user=user,
            )

        return payment

    @staticmethod
    def approve(payment, user):
        """审核通过供应商付款并回写采购单状态。"""
        if payment.status != "pending":
            raise ServiceError(
                "只有待审核状态才能审核",
                code=status.HTTP_400_BAD_REQUEST,
            )
        payment.status = "approved"
        payment.approved_by = user
        payment.approved_at = timezone.now()
        payment.save(update_fields=["status", "approved_by", "approved_at"])
        SupplierPaymentService.apply_payment(payment=payment)
        return payment

    @staticmethod
    def reject(payment, user, approval_comment: str = ""):
        """拒绝供应商付款。"""
        if payment.status != "pending":
            raise ServiceError(
                "只有待审核状态才能拒绝",
                code=status.HTTP_400_BAD_REQUEST,
            )
        payment.status = "rejected"
        payment.approved_by = user
        payment.approved_at = timezone.now()
        payment.approval_comment = approval_comment
        payment.save(
            update_fields=[
                "status",
                "approved_by",
                "approved_at",
                "approval_comment",
            ]
        )
        return payment
