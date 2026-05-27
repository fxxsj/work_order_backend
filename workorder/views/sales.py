"""
销售订单视图集

包含销售订单的视图集。
"""

from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django_filters import CharFilter, DateFromToRangeFilter, FilterSet
from rest_framework import status
from rest_framework.decorators import action
from workorder.response import APIResponse
from workorder.permission_utils import PermissionUtils
from workorder.docs.sales import (
    sales_order_approve_docs,
    sales_order_cancel_docs,
    sales_order_complete_docs,
    sales_order_docs,
    sales_order_item_docs,
    sales_order_reject_docs,
    sales_order_start_docs,
    sales_order_submit_docs,
    sales_order_summary_docs,
    sales_order_update_payment_docs,
)

from ..models.inventory import ProductStock
from ..models.products import Product
from ..models.sales import SalesOrder, SalesOrderItem
from ..serializers.sales import (
    SalesOrderDetailSerializer,
    SalesOrderItemSerializer,
    SalesOrderListSerializer,
)
from ..services.sales_order_status_service import SalesOrderStatusService
from .base_viewsets import BaseViewSet


class SalesOrderFilterSet(FilterSet):
    customer_name = CharFilter(field_name="customer__name", lookup_expr="icontains")
    order_date = DateFromToRangeFilter()
    delivery_date = DateFromToRangeFilter()
    actual_delivery_date = DateFromToRangeFilter()
    created_at = DateFromToRangeFilter()

    class Meta:
        model = SalesOrder
        fields = ["customer", "status", "payment_status"]


def _scope_sales_orders(queryset, user):
    if not user.is_authenticated:
        return queryset.none()
    if user.is_superuser or PermissionUtils.is_finance_user(user):
        return queryset

    scope = PermissionUtils.build_sales_order_scope_q(user, "")
    return queryset.filter(scope).distinct()


@sales_order_docs
class SalesOrderViewSet(BaseViewSet):
    """销售订单视图集"""

    queryset = SalesOrder.objects.all()
    search_fields = [
        "order_number",
        "customer__name",
        "customer__code",
        "contract_number",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "order_number",
        "customer__name",
        "status",
        "payment_status",
        "order_date",
        "delivery_date",
        "actual_delivery_date",
        "subtotal",
        "tax_amount",
        "discount_amount",
        "total_amount",
        "paid_amount",
        "payment_date",
        "items_count",
        "work_order_count",
    ]
    ordering = ["-created_at"]
    filterset_class = SalesOrderFilterSet

    def get_queryset(self):
        """优化查询"""
        queryset = SalesOrder.objects.select_related(
            "customer", "submitted_by", "approved_by", "created_by"
        ).prefetch_related("items", "items__product", "source_work_orders")
        queryset = queryset.annotate(
            items_count=Count("items", distinct=True),
            work_order_count=Count("source_work_orders", distinct=True),
        )
        return _scope_sales_orders(queryset, self.request.user)

    def get_serializer_class(self):
        """根据action选择序列化器"""
        if self.action == "list":
            return SalesOrderListSerializer
        return SalesOrderDetailSerializer

    def perform_create(self, serializer):
        """创建销售订单时自动设置创建人"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"])
    @sales_order_summary_docs
    def summary(self, request):
        """销售订单汇总"""
        queryset = self.filter_queryset(self.get_queryset())
        summary = queryset.aggregate(
            total_count=Count("id"),
            draft_count=Count("id", filter=Q(status="draft")),
            submitted_count=Count("id", filter=Q(status="submitted")),
            approved_count=Count("id", filter=Q(status="approved")),
            rejected_count=Count("id", filter=Q(status="rejected")),
            in_production_count=Count("id", filter=Q(status="in_production")),
            completed_count=Count("id", filter=Q(status="completed")),
            cancelled_count=Count("id", filter=Q(status="cancelled")),
        )
        status_stats = (
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )
        return APIResponse.success(data={"summary": summary, "by_status": list(status_stats)})

    @action(detail=True, methods=["post"])
    @sales_order_submit_docs
    def submit(self, request, pk=None):
        """提交销售订单"""
        sales_order = self.get_object()
        if sales_order.status not in ["draft", "rejected"]:
            return APIResponse.error(
                "只有草稿或已拒绝状态的订单才能提交", code=status.HTTP_400_BAD_REQUEST
            )

        # 验证订单数据完整性
        errors = sales_order.validate_before_approval()
        if errors:
            return APIResponse.error("订单数据验证失败", code=status.HTTP_400_BAD_REQUEST, errors=errors)

        # 更新订单状态
        sales_order.status = "submitted"
        sales_order.submitted_by = request.user
        sales_order.submitted_at = timezone.now()
        # 清理上次审核信息
        sales_order.approved_by = None
        sales_order.approved_at = None
        sales_order.approval_comment = ""
        sales_order.rejection_reason = ""
        sales_order.save()

        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @sales_order_approve_docs
    def approve(self, request, pk=None):
        """审核通过销售订单"""
        sales_order = self.get_object()
        if sales_order.status != "submitted":
            return APIResponse.error("只有已提交状态的订单才能审核", code=status.HTTP_400_BAD_REQUEST)

        # 再次验证订单数据完整性
        errors = sales_order.validate_before_approval()
        if errors:
            return APIResponse.error("订单数据验证失败", code=status.HTTP_400_BAD_REQUEST, errors=errors)

        # 更新订单状态
        sales_order.status = "approved"
        sales_order.approved_by = request.user
        sales_order.approved_at = timezone.now()
        sales_order.approval_comment = request.data.get("approval_comment", "")
        sales_order.completion_reason = ""
        sales_order.save()

        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @sales_order_reject_docs
    def reject(self, request, pk=None):
        """拒绝销售订单"""
        sales_order = self.get_object()
        if sales_order.status != "submitted":
            return APIResponse.error("只有已提交状态的订单才能拒绝", code=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get("reason")
        if not reason:
            return APIResponse.error("请提供拒绝原因", code=status.HTTP_400_BAD_REQUEST)

        # 更新订单状态为已拒绝
        sales_order.status = "rejected"
        sales_order.approved_by = request.user
        sales_order.approved_at = timezone.now()
        sales_order.approval_comment = request.data.get("approval_comment", "")
        sales_order.rejection_reason = reason
        sales_order.save()

        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @sales_order_start_docs
    def start_production(self, request, pk=None):
        """根据关联施工单同步生产状态。"""
        sales_order = self.get_object()
        if sales_order.status not in ["approved", "in_production"]:
            return APIResponse.error("只有已审核或生产中的订单才能同步生产状态", code=status.HTTP_400_BAD_REQUEST)
        if not sales_order.get_related_work_orders_queryset().exists():
            return APIResponse.error("请先创建施工单，系统会自动同步为生产中", code=status.HTTP_400_BAD_REQUEST)

        SalesOrderStatusService.sync_status(sales_order)

        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)

    def _check_stock_availability(self, sales_order):
        """检查库存是否充足

        Returns:
            tuple: (is_available, error_messages)
        """
        errors = []
        items = sales_order.items.select_related("product").all()
        product_ids = {item.product_id for item in items if item.product_id}

        available_map = {}
        if product_ids:
            stock_totals = (
                ProductStock.objects.filter(product_id__in=product_ids, status="in_stock")
                .values("product_id")
                .annotate(
                    available_quantity=Sum(F("quantity") - F("reserved_quantity"))
                )
            )
            for item in stock_totals:
                qty = item["available_quantity"] or 0
                if qty < 0:
                    qty = 0
                available_map[item["product_id"]] = qty

        for item in items:
            product = item.product
            if not product:
                continue
            available_qty = available_map.get(item.product_id)
            if available_qty is None:
                if hasattr(product, "get_available_group_stock"):
                    available_qty = product.get_available_group_stock()
                elif hasattr(product, "stock_quantity"):
                    available_qty = product.stock_quantity
                else:
                    available_qty = 0
            if available_qty < item.quantity:
                errors.append(
                    f"{product.name}库存不足（需要{item.quantity}，当前{available_qty}）"
                )

        return len(errors) == 0, errors

    def _reduce_product_stock(self, sales_order):
        """销售订单审核通过后，减少产品库存数量

        规则：
        - 遍历订单明细，减少对应产品的库存数量
        - 减少数量 = 订单明细的 quantity
        - 使用事务保证原子性
        """
        from django.db import transaction

        items = sales_order.items.all()

        # 按产品汇总数量
        product_quantities = {}
        for item in items:
            product_id = item.product.id
            if product_id not in product_quantities:
                product_quantities[product_id] = 0
            product_quantities[product_id] += item.quantity

        # 在事务中减少产品库存
        with transaction.atomic():
            for product_id, quantity in product_quantities.items():
                try:
                    product = Product.objects.select_for_update().get(id=product_id)
                    if hasattr(product, "reduce_stock"):
                        product.reduce_stock(
                            quantity=quantity,
                            user=None,
                            reason=f"销售订单{sales_order.order_number}审核通过，出库{quantity}{product.unit}",
                        )
                    elif hasattr(product, "stock_quantity"):
                        product.stock_quantity = max(0, product.stock_quantity - quantity)
                        product.save(update_fields=["stock_quantity"])
                except Product.DoesNotExist:
                    pass
                except ValueError as e:
                    # 记录库存不足警告但不阻止流程
                    import logging

                    logging.warning(f"库存扣减警告：{e}")

    def _restore_product_stock(self, sales_order):
        """取消已审核订单时恢复产品库存

        规则：
        - 仅当订单已经扣减过库存时才恢复
        - 使用事务保证原子性
        """
        from django.db import transaction

        # 只有已审核、生产中状态的订单才需要恢复库存
        if sales_order.status not in ["approved", "in_production"]:
            return

        items = sales_order.items.all()

        # 按产品汇总数量
        product_quantities = {}
        for item in items:
            product_id = item.product.id
            if product_id not in product_quantities:
                product_quantities[product_id] = 0
            product_quantities[product_id] += item.quantity

        # 在事务中恢复产品库存
        with transaction.atomic():
            for product_id, quantity in product_quantities.items():
                try:
                    product = Product.objects.select_for_update().get(id=product_id)
                    if hasattr(product, "add_stock"):
                        product.add_stock(
                            quantity=quantity,
                            user=None,
                            reason=f"销售订单{sales_order.order_number}取消，库存回滚{quantity}{product.unit}",
                        )
                    elif hasattr(product, "stock_quantity"):
                        product.stock_quantity = product.stock_quantity + quantity
                        product.save(update_fields=["stock_quantity"])
                except Product.DoesNotExist:
                    pass
                except Exception as e:
                    import logging

                    logging.warning(f"库存恢复警告：{e}")

    @action(detail=True, methods=["post"])
    @sales_order_complete_docs
    def complete(self, request, pk=None):
        """完成订单"""
        sales_order = self.get_object()
        if sales_order.status not in ["approved", "in_production"]:
            return APIResponse.error(
                "只有已审核或生产中的订单才能完成", code=status.HTTP_400_BAD_REQUEST
            )

        all_delivered = SalesOrderStatusService.all_items_delivered(sales_order)
        completion_reason = str(request.data.get("completion_reason", "")).strip()
        if not all_delivered and not completion_reason:
            return APIResponse.error(
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

        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @sales_order_cancel_docs
    def cancel(self, request, pk=None):
        """取消订单"""
        sales_order = self.get_object()
        if sales_order.status in ["completed", "cancelled"]:
            return APIResponse.error("已完成或已取消的订单不能再次取消", code=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get("reason", "")
        sales_order.status = "cancelled"
        sales_order.rejection_reason = reason
        sales_order.save()

        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @sales_order_update_payment_docs
    def update_payment(self, request, pk=None):
        """更新付款信息"""
        sales_order = self.get_object()
        paid_amount = request.data.get("paid_amount")
        payment_date = request.data.get("payment_date")

        if paid_amount is not None:
            if not payment_date:
                return APIResponse.error(
                    "更新已付金额时必须提供付款日期", code=status.HTTP_400_BAD_REQUEST
                )
            sales_order.paid_amount = Decimal(str(paid_amount))
            sales_order.payment_date = payment_date

        sales_order.save()  # save方法会自动更新payment_status

        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)


@sales_order_item_docs
class SalesOrderItemViewSet(BaseViewSet):
    """销售订单明细视图集"""

    queryset = SalesOrderItem.objects.all()
    serializer_class = SalesOrderItemSerializer
    filterset_fields = ["sales_order", "product"]
    ordering_fields = ["created_at"]
    ordering = ["sales_order", "id"]

    def get_queryset(self):
        """优化查询"""
        queryset = super().get_queryset().select_related("sales_order", "product")
        if not self.request.user.is_authenticated:
            return queryset.none()
        if self.request.user.is_superuser or PermissionUtils.is_finance_user(
            self.request.user
        ):
            return queryset

        scope = PermissionUtils.build_sales_order_scope_q(
            self.request.user, "sales_order"
        )
        return queryset.filter(scope).distinct()

    def perform_create(self, serializer):
        """创建明细后更新销售订单总金额"""
        item = serializer.save()
        item.sales_order.update_totals()

    def perform_update(self, serializer):
        """更新明细后更新销售订单总金额"""
        item = serializer.save()
        item.sales_order.update_totals()

    def perform_destroy(self, instance):
        """删除明细后更新销售订单总金额"""
        sales_order = instance.sales_order
        super().perform_destroy(instance)
        sales_order.update_totals()
