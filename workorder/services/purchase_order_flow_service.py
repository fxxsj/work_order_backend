"""采购单业务状态流转服务。"""

from django.db import transaction
from django.utils import timezone
from rest_framework import status

from workorder.constants.status import MaterialPurchaseStatus
from workorder.models.materials import PurchaseOrder
from workorder.services.service_errors import ServiceError


class PurchaseOrderStatus:
    """采购单业务状态常量。"""

    PENDING = "pending"
    ORDERED = "ordered"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class PurchaseOrderFlowService:
    """集中处理采购单业务状态推进。"""

    ALLOWED_STATUS_TRANSITIONS = {
        PurchaseOrderStatus.PENDING: [
            PurchaseOrderStatus.ORDERED,
            PurchaseOrderStatus.CANCELLED,
        ],
        PurchaseOrderStatus.ORDERED: [
            PurchaseOrderStatus.RECEIVED,
            PurchaseOrderStatus.CANCELLED,
        ],
        PurchaseOrderStatus.RECEIVED: [],
        PurchaseOrderStatus.CANCELLED: [],
    }

    @staticmethod
    @transaction.atomic
    def place_order(*, order: PurchaseOrder, ordered_date=None) -> PurchaseOrder:
        """将已审批采购单推进为已下单，并回写关联施工单物料状态。"""
        order.refresh_from_db()

        if order.approval_status != PurchaseOrder.Status.APPROVED:
            raise ServiceError(
                "只有已批准的采购单可以下单",
                code=status.HTTP_400_BAD_REQUEST,
            )

        if order.status != PurchaseOrderStatus.PENDING:
            raise ServiceError(
                "只有待下单的采购单可以下单",
                code=status.HTTP_400_BAD_REQUEST,
            )

        order.status = PurchaseOrderStatus.ORDERED
        order.ordered_date = ordered_date or timezone.now().date()
        order.save(update_fields=["status", "ordered_date", "updated_at"])

        for item in order.items.select_related("work_order_material").all():
            work_order_material = item.work_order_material
            if (
                work_order_material
                and work_order_material.purchase_status == MaterialPurchaseStatus.PENDING
            ):
                work_order_material.purchase_status = MaterialPurchaseStatus.ORDERED
                work_order_material.purchase_date = timezone.now().date()
                work_order_material.save(
                    update_fields=["purchase_status", "purchase_date"]
                )

        return order
