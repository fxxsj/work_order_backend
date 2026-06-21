"""
客户订单视图集

包含客户订单的视图集。
"""

from django.db.models import Count, Q
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

from ..models.sales import SalesOrder, SalesOrderItem
from ..serializers.sales import (
    SalesOrderDetailSerializer,
    SalesOrderItemSerializer,
    SalesOrderListSerializer,
)
from ..services.sales_order_service import SalesOrderService
from ._decorators import handle_service_error
from .base_viewsets import BaseViewSet
from .mixins import ApprovalTimelineMixin


class SalesOrderFilterSet(FilterSet):
    customer_name = CharFilter(field_name="customer__name", lookup_expr="icontains")
    order_date = DateFromToRangeFilter()
    delivery_date = DateFromToRangeFilter()
    actual_delivery_date = DateFromToRangeFilter()
    created_at = DateFromToRangeFilter()

    class Meta:
        model = SalesOrder
        fields = ["customer", "status", "approval_status", "payment_status"]


def _scope_sales_orders(queryset, user):
    if not user.is_authenticated:
        return queryset.none()
    if user.is_superuser or PermissionUtils.is_finance_user(user):
        return queryset

    scope = PermissionUtils.build_sales_order_scope_q(user, "")
    return queryset.filter(scope).distinct()


@sales_order_docs
class SalesOrderViewSet(ApprovalTimelineMixin, BaseViewSet):
    """客户订单视图集"""

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
        """创建客户订单时自动设置创建人"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"])
    @sales_order_summary_docs
    def summary(self, request):
        """客户订单汇总"""
        queryset = self.filter_queryset(self.get_queryset())
        return APIResponse.success(data=SalesOrderService.get_summary(queryset))

    @action(detail=True, methods=["post"])
    @sales_order_submit_docs
    @handle_service_error
    def submit(self, request, pk=None):
        """提交客户订单"""
        sales_order = self.get_object()
        SalesOrderService.submit_for_approval(
            sales_order=sales_order,
            user=request.user,
            auto_approve=request.data.get("auto_approve", False),
        )
        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @sales_order_approve_docs
    @handle_service_error
    def approve(self, request, pk=None):
        """审核通过客户订单"""
        sales_order = self.get_object()
        SalesOrderService.approve(
            sales_order=sales_order,
            user=request.user,
            comment=request.data.get("approval_comment", ""),
        )
        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @sales_order_reject_docs
    @handle_service_error
    def reject(self, request, pk=None):
        """拒绝客户订单"""
        sales_order = self.get_object()
        SalesOrderService.reject(
            sales_order=sales_order,
            user=request.user,
            reason=request.data.get("reason", ""),
            comment=request.data.get("approval_comment", ""),
        )
        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @sales_order_start_docs
    @handle_service_error
    def start_production(self, request, pk=None):
        """根据关联施工单同步生产状态。"""
        sales_order = self.get_object()
        SalesOrderService.start_production(sales_order=sales_order)
        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @sales_order_complete_docs
    @handle_service_error
    def complete(self, request, pk=None):
        """完成订单"""
        sales_order = self.get_object()
        SalesOrderService.complete(
            sales_order=sales_order,
            completion_reason=request.data.get("completion_reason", ""),
        )
        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @sales_order_cancel_docs
    @handle_service_error
    def cancel(self, request, pk=None):
        """取消订单"""
        sales_order = self.get_object()
        SalesOrderService.cancel(
            sales_order=sales_order,
            reason=request.data.get("reason", ""),
        )
        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @sales_order_update_payment_docs
    @handle_service_error
    def update_payment(self, request, pk=None):
        """更新付款信息"""
        sales_order = self.get_object()
        SalesOrderService.update_payment(
            sales_order=sales_order,
            paid_amount=request.data.get("paid_amount"),
            payment_date=request.data.get("payment_date"),
        )
        serializer = self.get_serializer(sales_order)
        return APIResponse.success(data=serializer.data)


@sales_order_item_docs
class SalesOrderItemViewSet(BaseViewSet):
    """客户订单明细视图集"""

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
        """创建明细后更新客户订单总金额"""
        item = serializer.save()
        item.sales_order.update_totals()

    def perform_update(self, serializer):
        """更新明细后更新客户订单总金额"""
        item = serializer.save()
        item.sales_order.update_totals()

    def perform_destroy(self, instance):
        """删除明细后更新客户订单总金额"""
        sales_order = instance.sales_order
        super().perform_destroy(instance)
        sales_order.update_totals()
