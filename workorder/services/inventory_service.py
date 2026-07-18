"""
库存业务服务

将 inventory.py 视图集中的业务逻辑下沉到服务层：
- ProductStockService：成品库存预警、汇总、调整
- StockInService：入库单提交、确认、汇总
- StockOutService：出库单提交、确认、汇总
- DeliveryOrderService：发货、签收、拒收、拒收后处理、汇总
- QualityInspectionService：质检完成、汇总

视图层只负责参数校验、序列化和响应包装。
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from rest_framework import status

from workorder.models import (
    DeliveryItem,
    DeliveryOrder,
    ProductStock,
    QualityInspection,
    SalesOrder,
    StockIn,
    StockOut,
)
from workorder.models.system import ApprovalConfig
from workorder.serializers.inventory import (
    upsert_delivery_exception_resolution,
)
from workorder.services.sales_order_status_service import (
    SalesOrderStatusService,
)

from .service_errors import ServiceError

logger = logging.getLogger(__name__)


class ProductStockService:
    """成品库存服务"""

    @staticmethod
    def get_low_stock(queryset):
        """返回低库存（可用数量 <= 最小库存）记录。"""
        return (
            queryset.filter(status="in_stock")
            .annotate(available=F("quantity") - F("reserved_quantity"))
            .filter(available__lte=F("min_stock_level"))
            .select_related("product")
        )

    @staticmethod
    def get_expired(queryset):
        """返回已过期库存记录。"""
        return queryset.filter(
            expiry_date__lt=timezone.now().date()
        ).select_related("product")

    @staticmethod
    def get_expiring_soon(queryset, days: int = 30):
        """返回即将过期（默认30天内）且仍在库的库存记录。"""
        threshold_date = timezone.now().date() + timedelta(days=days)
        return queryset.filter(
            expiry_date__lte=threshold_date,
            expiry_date__gt=timezone.now().date(),
            status="in_stock",
        ).select_related("product")

    @staticmethod
    def get_summary(queryset) -> dict:
        """库存汇总统计。"""
        stats = queryset.aggregate(
            total_quantity=Sum("quantity"),
            total_products=Count("product", distinct=True),
        )

        low_stock_count = (
            queryset.filter(status="in_stock")
            .annotate(available=F("quantity") - F("reserved_quantity"))
            .filter(available__lte=F("min_stock_level"))
            .count()
        )

        expired_count = queryset.filter(
            expiry_date__isnull=False, expiry_date__lt=timezone.now().date()
        ).count()

        return {
            "total_quantity": stats["total_quantity"] or 0,
            "total_products": stats["total_products"] or 0,
            "low_stock_count": low_stock_count,
            "expired_count": expired_count,
            "reserved_count": queryset.filter(status="reserved").count(),
            "quality_check_count": queryset.filter(
                status="quality_check"
            ).count(),
        }

    @staticmethod
    def adjust_stock(stock, adjust_type: str, quantity, reason: str) -> dict:
        """调整库存数量。

        Returns:
            {"old_quantity": float, "new_quantity": float,
             "stock": ProductStock}
        """
        old_quantity = stock.quantity

        if adjust_type == "add":
            stock.quantity += quantity
        elif adjust_type == "subtract":
            stock.quantity -= quantity
        elif adjust_type == "set":
            stock.quantity = quantity
        else:
            raise ServiceError(
                f"不支持的调整类型: {adjust_type}",
                code=status.HTTP_400_BAD_REQUEST,
            )

        adjustment_note = (
            f"库存调整: {old_quantity} -> {stock.quantity}, 原因: {reason}"
        )
        if stock.notes:
            stock.notes = f"{stock.notes}\n{adjustment_note}"
        else:
            stock.notes = adjustment_note

        stock.save()

        return {
            "old_quantity": float(old_quantity),
            "new_quantity": float(stock.quantity),
            "stock": stock,
        }


class StockInService:
    """入库单服务"""

    @staticmethod
    def submit(stock_in: StockIn, user) -> StockIn:
        """提交入库单。"""
        if stock_in.status != "draft":
            raise ServiceError(
                "只有草稿状态的入库单可以提交",
                code=status.HTTP_400_BAD_REQUEST,
            )

        stock_in.status = "submitted"
        stock_in.submitted_by = user
        stock_in.submitted_at = timezone.now()
        stock_in.save()

        # 模块审核开关：若入库单审核已关闭，系统自动确认
        if not ApprovalConfig.get_solo().is_enabled("stockin"):
            return StockInService.confirm(stock_in=stock_in, user=user)

        return stock_in

    @staticmethod
    def confirm(stock_in: StockIn, user) -> StockIn:
        """确认入库单并创建库存批次。"""
        if stock_in.status != "submitted":
            raise ServiceError(
                "只有已提交状态的入库单可以确认",
                code=status.HTTP_400_BAD_REQUEST,
            )

        work_order = stock_in.work_order
        related_purchase_orders = work_order.purchase_orders.exclude(
            status="cancelled"
        )
        if related_purchase_orders.exists():
            has_approved_po = related_purchase_orders.filter(
                status="approved"
            ).exists()
            if not has_approved_po:
                raise ServiceError(
                    "关联的采购单尚未审核通过，无法确认入库",
                    code=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            stock_in.status = "completed"
            stock_in.confirmed_by = user
            stock_in.confirmed_at = timezone.now()
            stock_in.save()

            for wp in work_order.products.select_related("product").all():
                if not wp.quantity or wp.quantity <= 0:
                    continue
                batch_no = f"{stock_in.order_number}-{wp.id}"
                ProductStock.objects.get_or_create(
                    batch_no=batch_no,
                    defaults={
                        "product": wp.product,
                        "quantity": wp.quantity,
                        "work_order": work_order,
                        "production_date": stock_in.stock_in_date,
                        "status": "in_stock",
                        "notes": f"入库单 {stock_in.order_number}",
                    },
                )

        return stock_in

    @staticmethod
    def get_summary(queryset) -> dict:
        """入库单汇总统计。"""
        summary = queryset.aggregate(
            total_count=Count("id"),
            draft_count=Count("id", filter=Q(status="draft")),
            submitted_count=Count("id", filter=Q(status="submitted")),
            completed_count=Count("id", filter=Q(status="completed")),
        )
        status_stats = (
            queryset.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )
        return {"summary": summary, "by_status": list(status_stats)}


class StockOutService:
    """出库单服务"""

    @staticmethod
    def submit(stock_out: StockOut, user) -> StockOut:
        """提交出库单。"""
        if stock_out.status != "draft":
            raise ServiceError(
                "只有草稿状态的出库单可以提交",
                code=status.HTTP_400_BAD_REQUEST,
            )

        stock_out.status = "submitted"
        stock_out.submitted_by = user
        stock_out.submitted_at = timezone.now()
        stock_out.save()

        # 模块审核开关：若出库单审核已关闭，系统自动确认
        if not ApprovalConfig.get_solo().is_enabled("stockout"):
            return StockOutService.confirm(stock_out=stock_out, user=user)

        return stock_out

    @staticmethod
    def confirm(stock_out: StockOut, user) -> StockOut:
        """确认出库单：扣减库存并更新送货单/销售订单明细。"""
        if stock_out.status != "submitted":
            raise ServiceError(
                "只有已提交状态的出库单可以确认",
                code=status.HTTP_400_BAD_REQUEST,
            )

        if stock_out.out_type != "delivery" or not stock_out.delivery_order_id:
            raise ServiceError(
                "当前仅支持【发货出库】的确认扣减库存",
                code=status.HTTP_400_BAD_REQUEST,
            )

        delivery_order = stock_out.delivery_order
        if delivery_order.status != "pending":
            raise ServiceError(
                "送货单不是【待发货】状态，无法再次扣减库存",
                code=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for item in delivery_order.items.select_related(
                "product",
                "sales_order_item",
            ).all():
                remaining = item.quantity

                if item.stock_batch:
                    stock = (
                        ProductStock.objects.select_for_update()
                        .filter(
                            batch_no=item.stock_batch,
                            product=item.product,
                            status="in_stock",
                        )
                        .first()
                    )
                    if not stock:
                        raise ServiceError(
                            f"库存批次不可用: {item.stock_batch}",
                            code=status.HTTP_400_BAD_REQUEST,
                        )

                    available = stock.quantity - stock.reserved_quantity
                    if available < remaining:
                        missing = remaining - available
                        raise ServiceError(
                            f"批次库存不足: {item.stock_batch} 缺少 {missing}",
                            code=status.HTTP_400_BAD_REQUEST,
                        )

                    stock.quantity -= remaining
                    stock.save(update_fields=["quantity", "updated_at"])
                    remaining = 0
                else:
                    stocks = (
                        ProductStock.objects.select_for_update()
                        .filter(product=item.product, status="in_stock")
                        .order_by("created_at")
                    )

                    for stock in stocks:
                        if remaining <= 0:
                            break
                        available = stock.quantity - stock.reserved_quantity
                        if available <= 0:
                            continue
                        deduct = min(available, remaining)
                        stock.quantity -= deduct
                        stock.save(update_fields=["quantity", "updated_at"])
                        remaining -= deduct

                if remaining > 0:
                    raise ServiceError(
                        f"产品 {item.product.name} 库存不足，缺少 {remaining}",
                        code=status.HTTP_400_BAD_REQUEST,
                    )

                if item.sales_order_item:
                    item.sales_order_item.delivered_quantity += item.quantity
                    item.sales_order_item.save(
                        update_fields=["delivered_quantity"]
                    )

            stock_out.status = "completed"
            stock_out.confirmed_by = user
            stock_out.confirmed_at = timezone.now()
            if not stock_out.operator_id:
                stock_out.operator = user
            stock_out.save()

            delivery_order.status = "shipped"
            if not delivery_order.delivery_date:
                delivery_order.delivery_date = timezone.now().date()
            delivery_order.save(
                update_fields=["status", "delivery_date", "updated_at"]
            )

        return stock_out

    @staticmethod
    def get_summary(queryset) -> dict:
        """出库单汇总统计。"""
        summary = queryset.aggregate(
            total_count=Count("id"),
            draft_count=Count("id", filter=Q(status="draft")),
            submitted_count=Count("id", filter=Q(status="submitted")),
            completed_count=Count("id", filter=Q(status="completed")),
        )
        status_stats = (
            queryset.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )
        return {"summary": summary, "by_status": list(status_stats)}


class DeliveryOrderService:
    """送货单服务"""

    @staticmethod
    def ship(
        delivery_order: DeliveryOrder,
        user,
        logistics_company: str = "",
        tracking_number: str = "",
    ) -> dict:
        """发货：扣减库存、创建出库单、更新销售订单状态。

        Returns:
            {"delivery_order": DeliveryOrder, "stock_out": StockOut}
        """
        if delivery_order.status != "pending":
            raise ServiceError(
                "只有待发货状态的送货单可以发货",
                code=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for item in delivery_order.items.all():
                stocks = ProductStock.objects.filter(
                    product=item.product,
                    status="in_stock",
                    quality_status__in=["qualified", "concession"],
                ).order_by("created_at")

                remaining = item.quantity
                for stock in stocks:
                    if remaining <= 0:
                        break
                    available = stock.quantity - stock.reserved_quantity
                    if available <= 0:
                        continue
                    deduct = min(available, remaining)
                    stock.quantity -= deduct
                    stock.save()
                    remaining -= deduct

                if remaining > 0:
                    pending_stock = (
                        ProductStock.objects.filter(
                            product=item.product,
                            status="in_stock",
                            quality_status="pending",
                        ).aggregate(total=Sum("quantity"))["total"]
                        or 0
                    )
                    unqualified_stock = (
                        ProductStock.objects.filter(
                            product=item.product,
                            status="in_stock",
                            quality_status="unqualified",
                        ).aggregate(total=Sum("quantity"))["total"]
                        or 0
                    )

                    message = f"产品 {item.product.name} 可发货库存不足，缺少 {remaining}"
                    if pending_stock > 0:
                        message += f"（另有 {pending_stock} 待检中）"
                    if unqualified_stock > 0:
                        message += f"（另有 {unqualified_stock} 不合格）"
                    raise ServiceError(
                        message,
                        code=status.HTTP_400_BAD_REQUEST,
                    )

                if item.sales_order_item:
                    item.sales_order_item.delivered_quantity += item.quantity
                    item.sales_order_item.save()

            stock_out = StockOut.objects.create(
                out_type="delivery",
                delivery_order=delivery_order,
                stock_out_date=timezone.now().date(),
                status="completed",
                operator=user,
                notes=f"送货单 {delivery_order.order_number} 自动出库",
            )

            delivery_order.status = "shipped"
            delivery_order.delivery_date = timezone.now().date()
            if logistics_company:
                delivery_order.logistics_company = logistics_company
            if tracking_number:
                delivery_order.tracking_number = tracking_number
            delivery_order.save()

            DeliveryOrderService._sync_sales_order_status(
                delivery_order.sales_order
            )

        return {"delivery_order": delivery_order, "stock_out": stock_out}

    @staticmethod
    def receive(
        delivery_order: DeliveryOrder,
        received_notes: str = "",
        receiver_signature=None,
    ) -> DeliveryOrder:
        """签收送货单。"""
        if delivery_order.status not in ["shipped", "in_transit"]:
            raise ServiceError(
                "只有已发货或运输中的送货单可以签收",
                code=status.HTTP_400_BAD_REQUEST,
            )

        delivery_order.status = "received"
        delivery_order.received_date = timezone.now()
        if received_notes:
            delivery_order.received_notes = received_notes
        if receiver_signature:
            delivery_order.receiver_signature = receiver_signature
        delivery_order.save()
        return delivery_order

    @staticmethod
    def reject(
        delivery_order: DeliveryOrder, reject_reason: str
    ) -> DeliveryOrder:
        """拒收送货单并回退库存。"""
        if delivery_order.status not in ["shipped", "in_transit"]:
            raise ServiceError(
                "只有已发货或运输中的送货单可以拒收",
                code=status.HTTP_400_BAD_REQUEST,
            )

        if not reject_reason:
            raise ServiceError(
                "请填写拒收原因",
                code=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for item in delivery_order.items.all():
                stock = (
                    ProductStock.objects.filter(
                        product=item.product, status="in_stock"
                    )
                    .order_by("-created_at")
                    .first()
                )

                if stock:
                    stock.quantity += item.quantity
                    stock.save()
                else:
                    ProductStock.objects.create(
                        product=item.product,
                        quantity=item.quantity,
                        batch_no=(
                            f"REJECT-{delivery_order.order_number}-{item.id}"
                        ),
                        status="in_stock",
                        notes=f"拒收回退: {delivery_order.order_number}",
                    )

                if item.sales_order_item:
                    item.sales_order_item.delivered_quantity -= item.quantity
                    if item.sales_order_item.delivered_quantity < 0:
                        item.sales_order_item.delivered_quantity = 0
                    item.sales_order_item.save()

            delivery_order.status = "rejected"
            delivery_order.received_notes = f"拒收原因: {reject_reason}"
            delivery_order.save()

            if delivery_order.sales_order:
                SalesOrderStatusService.sync_status(
                    delivery_order.sales_order,
                    preserve_manual_completion=False,
                )

        return delivery_order

    @staticmethod
    def resolve_exception(
        delivery_order: DeliveryOrder,
        resolution: str,
        resolution_notes: str,
        user,
    ) -> dict:
        """登记拒收后的处理动作。

        Returns:
            {"delivery_order": DeliveryOrder, **result_extra}
        """
        if delivery_order.status != "rejected":
            raise ServiceError(
                "只有拒收状态的送货单可以登记处理",
                code=status.HTTP_400_BAD_REQUEST,
            )

        resolution = (resolution or "").strip()
        resolution_notes = (resolution_notes or "").strip()
        if resolution not in {"reship", "rework", "terminate"}:
            raise ServiceError(
                "处理结论无效，可选：reship（补发）、rework（返工）、terminate（终止）",
                code=status.HTTP_400_BAD_REQUEST,
            )
        if not resolution_notes:
            raise ServiceError(
                "请填写处理说明",
                code=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            delivery_order.notes = upsert_delivery_exception_resolution(
                delivery_order.notes,
                resolution=resolution,
                resolution_notes=resolution_notes.replace("|", "/"),
                resolved_by=user.username or str(user.pk),
                resolved_at=timezone.now().strftime("%Y-%m-%d %H:%M"),
            )
            delivery_order.save(update_fields=["notes", "updated_at"])

            result_extra: dict[str, Any] = {}

            if resolution == "reship":
                reship_order = DeliveryOrder.objects.create(
                    sales_order=delivery_order.sales_order,
                    customer=delivery_order.customer,
                    delivery_date=timezone.now().date(),
                    receiver_name=delivery_order.receiver_name,
                    receiver_phone=delivery_order.receiver_phone,
                    delivery_address=delivery_order.delivery_address,
                    notes=(
                        f"拒收补发（原送货单：{delivery_order.order_number}）"
                        f"\n{resolution_notes}"
                    ),
                )
                for item in delivery_order.items.all():
                    DeliveryItem.objects.create(
                        delivery_order=reship_order,
                        product=item.product,
                        sales_order_item=item.sales_order_item,
                        quantity=item.quantity,
                        unit=item.unit,
                        unit_price=item.unit_price,
                    )
                result_extra["reship_order_id"] = reship_order.id
                result_extra["reship_order_number"] = reship_order.order_number

            elif resolution == "rework":
                from workorder.services.work_order_flow_service import (
                    WorkOrderFlowService,
                )

                sales_order = delivery_order.sales_order
                if sales_order:
                    try:
                        rework_work_order = (
                            WorkOrderFlowService.create_from_sales_order(
                                sales_order_id=sales_order.id,
                                production_quantity=None,
                                delivery_date=sales_order.delivery_date,
                                priority="urgent",
                                notes=(
                                    f"返工施工单（原送货单拒收："
                                    f"{delivery_order.order_number}）"
                                    f"\n{resolution_notes}"
                                ),
                                created_by=user,
                                additional_data={},
                            )
                        )
                        result_extra["rework_work_order_id"] = (
                            rework_work_order.id
                        )
                        result_extra["rework_work_order_number"] = (
                            rework_work_order.order_number
                        )
                    except Exception as e:
                        logger.warning(f"自动创建返工施工单失败: {e}")

            elif resolution == "terminate":
                sales_order = delivery_order.sales_order
                if sales_order and sales_order.status != "cancelled":
                    sales_order.status = "cancelled"
                    sales_order.completion_reason = (
                        f"送货单拒收后终止（{delivery_order.order_number}）"
                        f"\n{resolution_notes}"
                    )
                    sales_order.save(
                        update_fields=["status", "completion_reason"]
                    )
                    result_extra["sales_order_status"] = "cancelled"

        return {"delivery_order": delivery_order, **result_extra}

    @staticmethod
    def get_summary(queryset) -> dict:
        """送货单汇总统计。"""
        summary = queryset.aggregate(
            total_count=Count("id"),
            pending_count=Count("id", filter=Q(status="pending")),
            shipped_count=Count("id", filter=Q(status="shipped")),
            in_transit_count=Count("id", filter=Q(status="in_transit")),
            received_count=Count("id", filter=Q(status="received")),
            rejected_followup_count=Count(
                "id",
                filter=Q(status="rejected")
                & ~Q(notes__contains="[delivery_exception_resolution]"),
            ),
            pending_receive_count=Count(
                "id", filter=Q(status__in=["shipped", "in_transit"])
            ),
            pending_invoice_count=Count(
                "id",
                filter=Q(status__in=["shipped", "in_transit", "received"])
                & Q(sales_order__isnull=False)
                & Q(sales_order__invoices__isnull=True),
                distinct=True,
            ),
            total_freight=Sum("freight"),
        )

        status_stats = (
            queryset.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )

        return {"summary": summary, "by_status": list(status_stats)}

    @staticmethod
    def _sync_sales_order_status(sales_order: Optional[SalesOrder]) -> None:
        if not sales_order:
            return
        SalesOrderStatusService.sync_status(
            sales_order,
            preserve_manual_completion=False,
        )


class QualityInspectionService:
    """质量检验服务"""

    @staticmethod
    def complete(
        inspection: QualityInspection,
        result: str,
        passed_quantity: int = 0,
        failed_quantity: int = 0,
    ) -> QualityInspection:
        """完成质检并更新结果数量。"""
        if inspection.result != "pending":
            raise ServiceError(
                "该检验已经有结果了",
                code=status.HTTP_400_BAD_REQUEST,
            )

        if not result:
            raise ServiceError(
                "必须指定检验结果",
                code=status.HTTP_400_BAD_REQUEST,
            )

        inspection.result = result
        inspection.passed_quantity = passed_quantity
        inspection.failed_quantity = failed_quantity
        inspection.save()
        return inspection

    @staticmethod
    def get_summary(queryset) -> dict:
        """质检汇总统计。"""
        summary = queryset.aggregate(
            total_count=Count("id"),
            total_quantity=Sum("inspection_quantity"),
            total_passed=Sum("passed_quantity"),
            total_failed=Sum("failed_quantity"),
            avg_defective_rate=Sum("defective_rate") / Count("id"),
            pending_count=Count("id", filter=Q(result="pending")),
            unresolved_exception_count=Count(
                "id",
                filter=Q(result__in=["failed", "conditional"])
                & (Q(disposition="") | Q(disposition__isnull=True))
                & (
                    Q(disposition_notes="") | Q(disposition_notes__isnull=True)
                ),
            ),
        )

        result_stats = (
            queryset.values("result")
            .annotate(count=Count("id"))
            .order_by("result")
        )
        type_stats = (
            queryset.values("inspection_type")
            .annotate(count=Count("id"))
            .order_by("inspection_type")
        )

        return {
            "summary": summary,
            "by_result": list(result_stats),
            "by_type": list(type_stats),
        }
