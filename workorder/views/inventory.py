"""
库存相关视图集

包含库存管理的所有视图集：
- ProductStockViewSet: 成品库存
- StockInViewSet: 入库单
- StockOutViewSet: 出库单
- DeliveryOrderViewSet: 发货单
- DeliveryItemViewSet: 发货明细
- QualityInspectionViewSet: 质量检验
"""

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from workorder.permission_utils import PermissionUtils, apply_data_scope, apply_department_scope
from workorder.response import APIResponse
from workorder.docs.inventory import (
    delivery_item_docs,
    delivery_order_docs,
    delivery_receive_docs,
    delivery_reject_docs,
    delivery_ship_docs,
    delivery_summary_docs,
    product_stock_adjust_docs,
    product_stock_docs,
    product_stock_expired_docs,
    product_stock_expiring_docs,
    product_stock_low_docs,
    product_stock_summary_docs,
    quality_complete_docs,
    quality_inspection_docs,
    quality_summary_docs,
    stock_in_approve_docs,
    stock_in_docs,
    stock_in_summary_docs,
    stock_in_submit_docs,
    stock_out_approve_docs,
    stock_out_docs,
    stock_out_summary_docs,
)

from workorder.models import (
    DeliveryItem,
    DeliveryOrder,
    ProductStock,
    QualityInspection,
    SalesOrder,
    StockIn,
    StockOut,
)
from workorder.permissions import SuperuserFriendlyModelPermissions
from workorder.serializers.inventory import (
    DeliveryItemSerializer,
    DeliveryOrderCreateSerializer,
    DeliveryOrderListSerializer,
    DeliveryOrderSerializer,
    DeliveryOrderUpdateSerializer,
    ProductStockAdjustSerializer,
    ProductStockSerializer,
    ProductStockUpdateSerializer,
    QualityInspectionCreateSerializer,
    QualityInspectionSerializer,
    QualityInspectionUpdateSerializer,
    StockInCreateSerializer,
    StockInSerializer,
    StockOutSerializer,
    upsert_delivery_exception_resolution,
)
from workorder.services.sales_order_status_service import SalesOrderStatusService


def _apply_department_scope(queryset, department_id, path):
    return apply_department_scope(queryset, department_id, path)


def _apply_user_scope(
    queryset,
    user,
    *,
    customer_path=None,
    sales_order_path=None,
    work_order_path=None,
    ownership_paths=(),
):
    return apply_data_scope(
        queryset,
        user,
        customer_path=customer_path,
        sales_order_path=sales_order_path,
        work_order_path=work_order_path,
        ownership_paths=ownership_paths,
    )


@product_stock_docs
class ProductStockViewSet(viewsets.ModelViewSet):
    """成品库存视图集"""

    queryset = ProductStock.objects.select_related(
        "product", "work_order", "work_order__customer"
    ).all()
    serializer_class = ProductStockSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = [
        "created_at",
        "updated_at",
        "quantity",
        "reserved_quantity",
        "min_stock_level",
        "unit_cost",
        "location",
        "production_date",
        "expiry_date",
        "status",
        "batch_no",
        "product__name",
        "product__code",
        "work_order__order_number",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action in ["update", "partial_update"]:
            return ProductStockUpdateSerializer
        if self.action == "adjust":
            return ProductStockAdjustSerializer
        return ProductStockSerializer

    def get_queryset(self):
        """支持过滤和搜索"""
        queryset = super().get_queryset()

        # 按产品过滤
        product_id = self.request.query_params.get("product")
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        # 按状态过滤
        stock_status = self.request.query_params.get("status")
        if stock_status:
            queryset = queryset.filter(status=stock_status)

        # 按批次号过滤
        batch_number = self.request.query_params.get("batch_number")
        if batch_number:
            queryset = queryset.filter(batch_no__icontains=batch_number)

        # 搜索
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(batch_no__icontains=search)
                | Q(location__icontains=search)
                | Q(product__name__icontains=search)
                | Q(product__code__icontains=search)
                | Q(work_order__order_number__icontains=search)
                | Q(work_order__customer__name__icontains=search)
            )

        return queryset

    @action(detail=False, methods=["get"])
    @product_stock_low_docs
    def low_stock(self, request):
        """库存预警 - 使用模型的 min_stock_level 字段"""
        # 查询低库存产品（可用数量 <= 最小库存）
        low_stocks = (
            self.get_queryset()
            .filter(status="in_stock")
            .annotate(available=F("quantity") - F("reserved_quantity"))
            .filter(available__lte=F("min_stock_level"))
            .select_related("product")
        )

        serializer = self.get_serializer(low_stocks, many=True)
        return APIResponse.success(
            data={"count": low_stocks.count(), "results": serializer.data}
        )

    @action(detail=False, methods=["get"])
    @product_stock_expired_docs
    def expired(self, request):
        """已过期库存"""
        # 查询已过期的库存
        expired_stocks = (
            self.get_queryset()
            .filter(expiry_date__lt=timezone.now().date())
            .select_related("product")
        )

        serializer = self.get_serializer(expired_stocks, many=True)
        return APIResponse.success(
            data={"count": expired_stocks.count(), "results": serializer.data}
        )

    @action(detail=False, methods=["get"])
    @product_stock_expiring_docs
    def expiring_soon(self, request):
        """即将过期库存"""
        from datetime import timedelta

        # 默认30天内过期
        days = int(request.query_params.get("days", 30))
        threshold_date = timezone.now().date() + timedelta(days=days)

        expiring_stocks = (
            self.get_queryset()
            .filter(
                expiry_date__lte=threshold_date,
                expiry_date__gt=timezone.now().date(),
                status="in_stock",
            )
            .select_related("product")
        )

        serializer = self.get_serializer(expiring_stocks, many=True)
        return APIResponse.success(
            data={
                "count": expiring_stocks.count(),
                "threshold_date": threshold_date,
                "results": serializer.data,
            }
        )

    @action(detail=False, methods=["get"])
    @product_stock_summary_docs
    def summary(self, request):
        """库存汇总 - 匹配前端期望格式"""
        queryset = self.get_queryset()

        # 统计数据
        stats = queryset.aggregate(
            total_quantity=Sum("quantity"),
            total_products=Count("product", distinct=True),
        )

        # 低库存统计（可用数量 <= 最小库存）
        low_stock_count = (
            queryset.filter(status="in_stock")
            .annotate(available=F("quantity") - F("reserved_quantity"))
            .filter(available__lte=F("min_stock_level"))
            .count()
        )

        # 过期统计（只统计有过期日期的记录）
        expired_count = queryset.filter(
            expiry_date__isnull=False, expiry_date__lt=timezone.now().date()
        ).count()

        return APIResponse.success(
            data={
                "total_quantity": stats["total_quantity"] or 0,
                "total_products": stats["total_products"] or 0,
                "low_stock_count": low_stock_count,
                "expired_count": expired_count,
                "reserved_count": queryset.filter(status="reserved").count(),
                "quality_check_count": queryset.filter(status="quality_check").count(),
            }
        )

    @action(detail=True, methods=["post"])
    @product_stock_adjust_docs
    def adjust(self, request, pk=None):
        """库存调整"""
        stock = self.get_object()
        serializer = ProductStockAdjustSerializer(
            data=request.data, context={"stock": stock}
        )
        serializer.is_valid(raise_exception=True)

        adjust_type = serializer.validated_data["adjust_type"]
        quantity = serializer.validated_data["quantity"]
        reason = serializer.validated_data["reason"]

        old_quantity = stock.quantity

        # 执行调整
        if adjust_type == "add":
            stock.quantity += quantity
        elif adjust_type == "subtract":
            stock.quantity -= quantity
        else:  # set
            stock.quantity = quantity

        # 添加调整备注
        adjustment_note = (
            f"库存调整: {old_quantity} -> {stock.quantity}, 原因: {reason}"
        )
        if stock.notes:
            stock.notes = f"{stock.notes}\n{adjustment_note}"
        else:
            stock.notes = adjustment_note

        stock.save()

        return APIResponse.success(
            data={
                "message": "库存调整成功",
                "old_quantity": float(old_quantity),
                "new_quantity": float(stock.quantity),
                "data": ProductStockSerializer(stock).data,
            }
        )


@stock_in_docs
class StockInViewSet(viewsets.ModelViewSet):
    """入库单视图集"""

    queryset = StockIn.objects.select_related(
        "work_order",
        "work_order__customer",
        "operator",
        "submitted_by",
        "approved_by",
    ).all()
    serializer_class = StockInSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = [
        "order_number",
        "work_order__order_number",
        "work_order__customer__name",
        "stock_in_date",
        "status",
        "operator__username",
        "submitted_at",
        "approved_at",
        "created_at",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action == "create":
            return StockInCreateSerializer
        return StockInSerializer

    def get_queryset(self):
        """支持过滤"""
        queryset = super().get_queryset()

        # 按状态过滤
        stockin_status = self.request.query_params.get("status")
        if stockin_status:
            queryset = queryset.filter(status=stockin_status)

        # 按日期范围过滤
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(stock_in_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(stock_in_date__lte=end_date)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search)
                | Q(work_order__order_number__icontains=search)
                | Q(work_order__customer__name__icontains=search)
            )

        return queryset

    @action(detail=True, methods=["post"])
    @stock_in_submit_docs
    def submit(self, request, pk=None):
        """提交入库单"""
        stock_in = self.get_object()

        if stock_in.status != "draft":
            return APIResponse.error(
                "只有草稿状态的入库单可以提交", code=status.HTTP_400_BAD_REQUEST
            )

        stock_in.status = "submitted"
        stock_in.submitted_by = request.user
        stock_in.submitted_at = timezone.now()
        stock_in.save()

        serializer = self.get_serializer(stock_in)
        return APIResponse.success(data=serializer.data, message="入库单提交成功")

    @action(detail=True, methods=["post"])
    @stock_in_approve_docs
    def approve(self, request, pk=None):
        """审核入库单"""
        stock_in = self.get_object()

        if stock_in.status != "submitted":
            return APIResponse.error(
                "只有已提交状态的入库单可以审核", code=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            stock_in.status = "completed"
            stock_in.approved_by = request.user
            stock_in.approved_at = timezone.now()
            stock_in.save()

            # 创建 ProductStock 记录（按施工单产品拆分批次）
            work_order = stock_in.work_order
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

        serializer = self.get_serializer(stock_in)
        return APIResponse.success(data=serializer.data, message="入库单审核成功")

    @action(detail=False, methods=["get"])
    @stock_in_summary_docs
    def summary(self, request):
        """入库单汇总"""
        queryset = self.get_queryset()
        summary = queryset.aggregate(
            total_count=Count("id"),
            draft_count=Count("id", filter=Q(status="draft")),
            submitted_count=Count("id", filter=Q(status="submitted")),
            completed_count=Count("id", filter=Q(status="completed")),
        )
        status_stats = (
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )
        return APIResponse.success(
            data={"summary": summary, "by_status": list(status_stats)}
        )


@stock_out_docs
class StockOutViewSet(viewsets.ModelViewSet):
    """出库单视图集"""

    queryset = StockOut.objects.select_related(
        "delivery_order",
        "delivery_order__customer",
        "operator",
        "submitted_by",
        "approved_by",
    ).all()
    serializer_class = StockOutSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]

    def get_queryset(self):
        """支持过滤"""
        queryset = super().get_queryset()

        # 按状态过滤
        stockout_status = self.request.query_params.get("status")
        if stockout_status:
            queryset = queryset.filter(status=stockout_status)

        # 按出库类型过滤
        out_type = self.request.query_params.get("out_type")
        if out_type:
            queryset = queryset.filter(out_type=out_type)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search)
                | Q(delivery_order__order_number__icontains=search)
                | Q(delivery_order__customer__name__icontains=search)
            )

        return queryset

    @action(detail=True, methods=["post"])
    @stock_out_approve_docs
    def approve(self, request, pk=None):
        """审核出库单"""
        stock_out = self.get_object()

        if stock_out.status != "submitted":
            return APIResponse.error(
                "只有已提交状态的出库单可以审核", code=status.HTTP_400_BAD_REQUEST
            )

        if stock_out.out_type != "delivery" or not stock_out.delivery_order_id:
            return APIResponse.error(
                "当前仅支持【发货出库】的审核扣减库存", code=status.HTTP_400_BAD_REQUEST
            )

        delivery_order = stock_out.delivery_order
        if delivery_order.status != "pending":
            return APIResponse.error(
                "发货单不是【待发货】状态，无法再次扣减库存",
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
                        return APIResponse.error(
                            f"库存批次不可用: {item.stock_batch}",
                            code=status.HTTP_400_BAD_REQUEST,
                        )

                    available = stock.quantity - stock.reserved_quantity
                    if available < remaining:
                        missing = remaining - available
                        return APIResponse.error(
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
                    return APIResponse.error(
                        f"产品 {item.product.name} 库存不足，缺少 {remaining}",
                        code=status.HTTP_400_BAD_REQUEST,
                    )

                if item.sales_order_item:
                    item.sales_order_item.delivered_quantity += item.quantity
                    item.sales_order_item.save(update_fields=["delivered_quantity"])

            stock_out.status = "completed"
            stock_out.approved_by = request.user
            stock_out.approved_at = timezone.now()
            if not stock_out.operator_id:
                stock_out.operator = request.user
            stock_out.save()

            delivery_order.status = "shipped"
            if not delivery_order.delivery_date:
                delivery_order.delivery_date = timezone.now().date()
            delivery_order.save(update_fields=["status", "delivery_date", "updated_at"])

        serializer = self.get_serializer(stock_out)
        return APIResponse.success(data=serializer.data, message="出库单审核成功")

    @action(detail=False, methods=["get"])
    @stock_out_summary_docs
    def summary(self, request):
        """出库单汇总"""
        queryset = self.get_queryset()
        summary = queryset.aggregate(
            total_count=Count("id"),
            draft_count=Count("id", filter=Q(status="draft")),
            submitted_count=Count("id", filter=Q(status="submitted")),
            completed_count=Count("id", filter=Q(status="completed")),
        )
        status_stats = (
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )
        return APIResponse.success(
            data={"summary": summary, "by_status": list(status_stats)}
        )


@delivery_item_docs
class DeliveryItemViewSet(viewsets.ModelViewSet):
    """发货明细视图集"""

    queryset = DeliveryItem.objects.select_related("product").all()
    serializer_class = DeliveryItemSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]

    def get_queryset(self):
        """支持过滤"""
        queryset = super().get_queryset()

        # 按发货单过滤
        delivery_order_id = self.request.query_params.get("delivery_order")
        if delivery_order_id:
            queryset = queryset.filter(delivery_order_id=delivery_order_id)

        return queryset


@delivery_order_docs
class DeliveryOrderViewSet(viewsets.ModelViewSet):
    """发货单视图集"""

    queryset = (
        DeliveryOrder.objects.select_related("customer", "sales_order", "created_by")
        .prefetch_related("items__product")
        .all()
    )
    serializer_class = DeliveryOrderSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = [
        "order_number",
        "customer__name",
        "sales_order__order_number",
        "delivery_date",
        "status",
        "logistics_company",
        "tracking_number",
        "freight",
        "package_count",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action == "list":
            return DeliveryOrderListSerializer
        elif self.action == "create":
            return DeliveryOrderCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return DeliveryOrderUpdateSerializer
        return DeliveryOrderSerializer

    def get_queryset(self):
        """支持过滤和搜索"""
        queryset = super().get_queryset()
        queryset = _apply_user_scope(
            queryset,
            self.request.user,
            customer_path="customer",
            sales_order_path="sales_order",
            ownership_paths=("created_by",),
        )
        department_id = self.request.query_params.get("department_id")
        queryset = _apply_department_scope(
            queryset,
            department_id,
            "sales_order__source_work_orders__order_processes__department",
        )

        # 按状态过滤
        delivery_status = self.request.query_params.get("status")
        if delivery_status:
            queryset = queryset.filter(status=delivery_status)

        todo_filter = (self.request.query_params.get("todo") or "").strip()
        if todo_filter == "rejected_followup":
            queryset = queryset.filter(status="rejected").exclude(
                notes__contains="[delivery_exception_resolution]"
            )
        elif todo_filter == "pending_receive":
            queryset = queryset.filter(status__in=["shipped", "in_transit"])
        elif todo_filter == "pending_invoice":
            queryset = queryset.filter(
                status__in=["shipped", "in_transit", "received"],
                sales_order__isnull=False,
                sales_order__invoices__isnull=True,
            ).distinct()

        # 按客户过滤
        customer_id = self.request.query_params.get("customer")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # 按日期范围过滤
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(delivery_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(delivery_date__lte=end_date)

        # 搜索
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search)
                | Q(customer__name__icontains=search)
                | Q(logistics_company__icontains=search)
                | Q(tracking_number__icontains=search)
            )

        return queryset

    @action(detail=True, methods=["post"])
    @delivery_ship_docs
    def ship(self, request, pk=None):
        """发货 - 包含库存扣减逻辑"""
        delivery_order = self.get_object()

        if delivery_order.status != "pending":
            return APIResponse.error(
                "只有待发货状态的发货单可以发货", code=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # 1. 校验并扣减库存
            for item in delivery_order.items.all():
                # 查找可用库存（FIFO - 先进先出）
                stocks = ProductStock.objects.filter(
                    product=item.product, status="in_stock"
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
                    return APIResponse.error(
                        f"产品 {item.product.name} 库存不足，缺少 {remaining}",
                        code=status.HTTP_400_BAD_REQUEST,
                    )

                # 2. 更新销售订单明细已发货数量
                if item.sales_order_item:
                    item.sales_order_item.delivered_quantity += item.quantity
                    item.sales_order_item.save()

            # 3. 创建出库单
            stock_out = StockOut.objects.create(
                out_type="delivery",
                delivery_order=delivery_order,
                stock_out_date=timezone.now().date(),
                status="completed",
                operator=request.user,
                notes=f"发货单 {delivery_order.order_number} 自动出库",
            )

            # 4. 更新发货信息
            delivery_order.status = "shipped"
            delivery_order.delivery_date = timezone.now().date()

            # 获取物流信息
            logistics_company = request.data.get("logistics_company")
            tracking_number = request.data.get("tracking_number")
            if logistics_company:
                delivery_order.logistics_company = logistics_company
            if tracking_number:
                delivery_order.tracking_number = tracking_number

            delivery_order.save()

            # 5. 检查销售订单是否全部发货完成
            self._update_sales_order_status(delivery_order.sales_order)

        serializer = self.get_serializer(delivery_order)
        return APIResponse.success(
            data={
                "message": "发货成功",
                "stock_out_number": stock_out.order_number,
                "data": serializer.data,
            }
        )

    def _update_sales_order_status(self, sales_order):
        """更新销售订单发货状态"""
        if not sales_order:
            return
        SalesOrderStatusService.sync_status(
            sales_order,
            preserve_manual_completion=False,
        )

    @action(detail=True, methods=["post"])
    @delivery_receive_docs
    def receive(self, request, pk=None):
        """签收"""
        delivery_order = self.get_object()

        if delivery_order.status not in ["shipped", "in_transit"]:
            return APIResponse.error(
                "只有已发货或运输中的发货单可以签收", code=status.HTTP_400_BAD_REQUEST
            )

        # 更新签收信息
        delivery_order.status = "received"
        delivery_order.received_date = timezone.now()

        # 获取签收备注
        received_notes = request.data.get("received_notes")
        if received_notes:
            delivery_order.received_notes = received_notes

        receiver_signature = request.FILES.get("receiver_signature")
        if receiver_signature:
            delivery_order.receiver_signature = receiver_signature

        delivery_order.save()

        serializer = self.get_serializer(delivery_order)
        return APIResponse.success(data=serializer.data, message="签收成功")

    @action(detail=True, methods=["post"])
    @delivery_reject_docs
    def reject(self, request, pk=None):
        """拒收 - 库存回退"""
        delivery_order = self.get_object()

        if delivery_order.status not in ["shipped", "in_transit"]:
            return APIResponse.error(
                "只有已发货或运输中的发货单可以拒收", code=status.HTTP_400_BAD_REQUEST
            )

        reject_reason = request.data.get("reject_reason", "")
        if not reject_reason:
            return APIResponse.error("请填写拒收原因", code=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # 1. 回退库存
            for item in delivery_order.items.all():
                # 查找该产品最新的库存记录，或创建新的
                stock = (
                    ProductStock.objects.filter(product=item.product, status="in_stock")
                    .order_by("-created_at")
                    .first()
                )

                if stock:
                    # 回加到现有库存
                    stock.quantity += item.quantity
                    stock.save()
                else:
                    # 创建新的库存记录
                    ProductStock.objects.create(
                        product=item.product,
                        quantity=item.quantity,
                        batch_no=f"REJECT-{delivery_order.order_number}-{item.id}",
                        status="in_stock",
                        notes=f"拒收回退: {delivery_order.order_number}",
                    )

                # 2. 回退销售订单明细的已发货数量
                if item.sales_order_item:
                    item.sales_order_item.delivered_quantity -= item.quantity
                    if item.sales_order_item.delivered_quantity < 0:
                        item.sales_order_item.delivered_quantity = 0
                    item.sales_order_item.save()

            # 3. 更新发货单状态
            delivery_order.status = "rejected"
            delivery_order.received_notes = f"拒收原因: {reject_reason}"
            delivery_order.save()

            # 4. 更新销售订单状态
            if delivery_order.sales_order:
                SalesOrderStatusService.sync_status(
                    delivery_order.sales_order,
                    preserve_manual_completion=False,
                )

        serializer = self.get_serializer(delivery_order)
        return APIResponse.success(
            data=serializer.data, message="拒收处理成功，库存已回退"
        )

    @action(detail=True, methods=["post"])
    def resolve_exception(self, request, pk=None):
        """登记拒收后的处理动作"""
        delivery_order = self.get_object()

        if delivery_order.status != "rejected":
            return APIResponse.error(
                "只有拒收状态的发货单可以登记处理", code=status.HTTP_400_BAD_REQUEST
            )

        resolution = (request.data.get("resolution") or "").strip()
        resolution_notes = (request.data.get("resolution_notes") or "").strip()
        if resolution not in {"reship", "terminate"}:
            return APIResponse.error("处理结论无效", code=status.HTTP_400_BAD_REQUEST)
        if not resolution_notes:
            return APIResponse.error("请填写处理说明", code=status.HTTP_400_BAD_REQUEST)

        delivery_order.notes = upsert_delivery_exception_resolution(
            delivery_order.notes,
            resolution=resolution,
            resolution_notes=resolution_notes.replace("|", "/"),
            resolved_by=request.user.username or str(request.user.pk),
            resolved_at=timezone.now().strftime("%Y-%m-%d %H:%M"),
        )
        delivery_order.save(update_fields=["notes", "updated_at"])

        serializer = self.get_serializer(delivery_order)
        return APIResponse.success(data=serializer.data, message="拒收处理已登记")

    @action(detail=False, methods=["get"])
    @delivery_summary_docs
    def summary(self, request):
        """发货汇总"""
        queryset = self.get_queryset()

        # 统计数据
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

        # 按状态统计
        status_stats = (
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )

        return APIResponse.success(
            data={"summary": summary, "by_status": list(status_stats)}
        )


@quality_inspection_docs
class QualityInspectionViewSet(viewsets.ModelViewSet):
    """质量检验视图集"""

    queryset = QualityInspection.objects.select_related(
        "work_order", "work_order__customer", "product", "inspector"
    ).all()
    serializer_class = QualityInspectionSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = [
        "inspection_number",
        "inspection_type",
        "work_order__order_number",
        "work_order__customer__name",
        "product__name",
        "batch_no",
        "inspection_date",
        "inspector__username",
        "result",
        "inspection_quantity",
        "passed_quantity",
        "failed_quantity",
        "defective_rate",
        "created_at",
    ]
    ordering = ["-inspection_date"]

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action == "create":
            return QualityInspectionCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return QualityInspectionUpdateSerializer
        return QualityInspectionSerializer

    def get_queryset(self):
        """支持过滤和搜索"""
        queryset = super().get_queryset()
        queryset = _apply_user_scope(
            queryset,
            self.request.user,
            work_order_path="work_order",
            ownership_paths=("inspector",),
        )
        department_id = self.request.query_params.get("department_id")
        queryset = _apply_department_scope(
            queryset,
            department_id,
            "work_order__order_processes__department",
        )

        # 按检验类型过滤
        inspection_type = self.request.query_params.get("type")
        if inspection_type:
            queryset = queryset.filter(inspection_type=inspection_type)

        # 按结果过滤
        result = self.request.query_params.get("result")
        if result:
            queryset = queryset.filter(result=result)

        todo_filter = (self.request.query_params.get("todo") or "").strip()
        if todo_filter == "exception_followup":
            queryset = queryset.filter(result__in=["failed", "conditional"]).filter(
                Q(disposition="") | Q(disposition__isnull=True),
                Q(disposition_notes="") | Q(disposition_notes__isnull=True),
            )

        # 按日期范围过滤
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(inspection_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(inspection_date__lte=end_date)

        # 搜索
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(inspection_number__icontains=search)
                | Q(batch_no__icontains=search)
                | Q(product__name__icontains=search)
                | Q(work_order__order_number__icontains=search)
                | Q(work_order__customer__name__icontains=search)
            )

        return queryset

    @action(detail=True, methods=["post"])
    @quality_complete_docs
    def complete(self, request, pk=None):
        """完成检验"""
        inspection = self.get_object()

        if inspection.result != "pending":
            return APIResponse.error(
                "该检验已经有结果了", code=status.HTTP_400_BAD_REQUEST
            )

        # 获取检验结果
        result = request.data.get("result")
        if not result:
            return APIResponse.error(
                "必须指定检验结果", code=status.HTTP_400_BAD_REQUEST
            )

        inspection.result = result

        # 更新数量
        passed_quantity = request.data.get("passed_quantity", 0)
        failed_quantity = request.data.get("failed_quantity", 0)
        inspection.passed_quantity = passed_quantity
        inspection.failed_quantity = failed_quantity

        # 保存（会自动计算不良率）
        inspection.save()

        serializer = self.get_serializer(inspection)
        return APIResponse.success(data=serializer.data, message="检验完成")

    @action(detail=False, methods=["get"])
    @quality_summary_docs
    def summary(self, request):
        """质检汇总"""
        queryset = self.get_queryset()

        # 统计数据
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
                & (Q(disposition_notes="") | Q(disposition_notes__isnull=True)),
            ),
        )

        # 按结果统计
        result_stats = (
            queryset.values("result").annotate(count=Count("id")).order_by("result")
        )

        # 按类型统计
        type_stats = (
            queryset.values("inspection_type")
            .annotate(count=Count("id"))
            .order_by("inspection_type")
        )

        return APIResponse.success(
            data={
                "summary": summary,
                "by_result": list(result_stats),
                "by_type": list(type_stats),
            }
        )
