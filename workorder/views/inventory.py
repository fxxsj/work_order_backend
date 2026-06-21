"""
库存相关视图集

包含库存管理的所有视图集：
- ProductStockViewSet: 成品库存
- StockInViewSet: 入库单
- StockOutViewSet: 出库单
- DeliveryOrderViewSet: 送货单
- DeliveryItemViewSet: 送货明细
- QualityInspectionViewSet: 质量检验
"""

from datetime import timedelta

from django.db.models import Q
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
    stock_in_confirm_docs,
    stock_in_docs,
    stock_in_submit_docs,
    stock_in_summary_docs,
    stock_out_confirm_docs,
    stock_out_docs,
    stock_out_summary_docs,
)

from workorder.models import (
    DeliveryItem,
    DeliveryOrder,
    ProductStock,
    QualityInspection,
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
    StockOutCreateSerializer,
    StockOutSerializer,
)
from ..services.inventory_service import (
    DeliveryOrderService,
    ProductStockService,
    QualityInspectionService,
    StockInService,
    StockOutService,
)
from ._decorators import handle_service_error


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
        low_stocks = ProductStockService.get_low_stock(self.get_queryset())
        serializer = self.get_serializer(low_stocks, many=True)
        return APIResponse.success(
            data={"count": low_stocks.count(), "results": serializer.data}
        )

    @action(detail=False, methods=["get"])
    @product_stock_expired_docs
    def expired(self, request):
        """已过期库存"""
        expired_stocks = ProductStockService.get_expired(self.get_queryset())
        serializer = self.get_serializer(expired_stocks, many=True)
        return APIResponse.success(
            data={"count": expired_stocks.count(), "results": serializer.data}
        )

    @action(detail=False, methods=["get"])
    @product_stock_expiring_docs
    def expiring_soon(self, request):
        """即将过期库存"""
        days = int(request.query_params.get("days", 30))
        threshold_date = timezone.now().date() + timedelta(days=days)
        expiring_stocks = ProductStockService.get_expiring_soon(
            self.get_queryset(), days=days
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
        data = ProductStockService.get_summary(self.get_queryset())
        return APIResponse.success(data=data)

    @action(detail=True, methods=["post"])
    @product_stock_adjust_docs
    @handle_service_error
    def adjust(self, request, pk=None):
        """库存调整"""
        stock = self.get_object()
        serializer = ProductStockAdjustSerializer(
            data=request.data, context={"stock": stock}
        )
        serializer.is_valid(raise_exception=True)

        result = ProductStockService.adjust_stock(
            stock=stock,
            adjust_type=serializer.validated_data["adjust_type"],
            quantity=serializer.validated_data["quantity"],
            reason=serializer.validated_data["reason"],
        )

        return APIResponse.success(
            data={
                "message": "库存调整成功",
                "old_quantity": result["old_quantity"],
                "new_quantity": result["new_quantity"],
                "data": ProductStockSerializer(result["stock"]).data,
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
        "confirmed_by",
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
    @handle_service_error
    def submit(self, request, pk=None):
        """提交入库单"""
        stock_in = self.get_object()
        StockInService.submit(stock_in=stock_in, user=request.user)
        serializer = self.get_serializer(stock_in)
        return APIResponse.success(data=serializer.data, message="入库单提交成功")

    @action(detail=True, methods=["post"])
    @stock_in_confirm_docs
    @handle_service_error
    def confirm(self, request, pk=None):
        """确认入库单"""
        stock_in = self.get_object()
        StockInService.confirm(stock_in=stock_in, user=request.user)
        serializer = self.get_serializer(stock_in)
        return APIResponse.success(data=serializer.data, message="入库单确认成功")

    @action(detail=False, methods=["get"])
    @stock_in_summary_docs
    def summary(self, request):
        """入库单汇总"""
        data = StockInService.get_summary(self.get_queryset())
        return APIResponse.success(data=data)


@stock_out_docs
class StockOutViewSet(viewsets.ModelViewSet):
    """出库单视图集"""

    queryset = StockOut.objects.select_related(
        "delivery_order",
        "delivery_order__customer",
        "operator",
        "submitted_by",
        "confirmed_by",
    ).all()
    serializer_class = StockOutSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = [
        "order_number",
        "out_type",
        "delivery_order__order_number",
        "delivery_order__customer__name",
        "stock_out_date",
        "status",
        "operator__username",
        "submitted_at",
        "approved_at",
        "created_at",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action in ["create", "update", "partial_update"]:
            return StockOutCreateSerializer
        return StockOutSerializer

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

        # 按日期范围过滤
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(stock_out_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(stock_out_date__lte=end_date)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search)
                | Q(delivery_order__order_number__icontains=search)
                | Q(delivery_order__customer__name__icontains=search)
            )

        return queryset

    @action(detail=True, methods=["post"])
    @handle_service_error
    def submit(self, request, pk=None):
        """提交出库单"""
        stock_out = self.get_object()
        StockOutService.submit(stock_out=stock_out, user=request.user)
        serializer = self.get_serializer(stock_out)
        return APIResponse.success(data=serializer.data, message="出库单提交成功")

    @action(detail=True, methods=["post"])
    @stock_out_confirm_docs
    @handle_service_error
    def confirm(self, request, pk=None):
        """确认出库单"""
        stock_out = self.get_object()
        StockOutService.confirm(stock_out=stock_out, user=request.user)
        serializer = self.get_serializer(stock_out)
        return APIResponse.success(data=serializer.data, message="出库单确认成功")

    @action(detail=False, methods=["get"])
    @stock_out_summary_docs
    def summary(self, request):
        """出库单汇总"""
        data = StockOutService.get_summary(self.get_queryset())
        return APIResponse.success(data=data)


@delivery_item_docs
class DeliveryItemViewSet(viewsets.ModelViewSet):
    """发货明细视图集"""

    queryset = DeliveryItem.objects.select_related("product").all()
    serializer_class = DeliveryItemSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]

    def get_queryset(self):
        """支持过滤"""
        queryset = super().get_queryset()

        # 按送货单过滤
        delivery_order_id = self.request.query_params.get("delivery_order")
        if delivery_order_id:
            queryset = queryset.filter(delivery_order_id=delivery_order_id)

        return queryset


@delivery_order_docs
class DeliveryOrderViewSet(viewsets.ModelViewSet):
    """送货单视图集"""

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
    @handle_service_error
    def ship(self, request, pk=None):
        """发货 - 包含库存扣减逻辑"""
        delivery_order = self.get_object()
        result = DeliveryOrderService.ship(
            delivery_order=delivery_order,
            user=request.user,
            logistics_company=request.data.get("logistics_company", ""),
            tracking_number=request.data.get("tracking_number", ""),
        )
        serializer = self.get_serializer(result["delivery_order"])
        return APIResponse.success(
            data={
                "message": "发货成功",
                "stock_out_number": result["stock_out"].order_number,
                "data": serializer.data,
            }
        )

    @action(detail=True, methods=["post"])
    @delivery_receive_docs
    @handle_service_error
    def receive(self, request, pk=None):
        """签收"""
        delivery_order = self.get_object()
        delivery_order = DeliveryOrderService.receive(
            delivery_order=delivery_order,
            received_notes=request.data.get("received_notes"),
            receiver_signature=request.FILES.get("receiver_signature"),
        )
        serializer = self.get_serializer(delivery_order)
        return APIResponse.success(data=serializer.data, message="签收成功")

    @action(detail=True, methods=["post"])
    @delivery_reject_docs
    @handle_service_error
    def reject(self, request, pk=None):
        """拒收 - 库存回退"""
        delivery_order = self.get_object()
        delivery_order = DeliveryOrderService.reject(
            delivery_order=delivery_order,
            reject_reason=request.data.get("reject_reason", ""),
        )
        serializer = self.get_serializer(delivery_order)
        return APIResponse.success(
            data=serializer.data, message="拒收处理成功，库存已回退"
        )

    @action(detail=True, methods=["post"])
    @handle_service_error
    def resolve_exception(self, request, pk=None):
        """
        登记拒收后的处理动作，并驱动后续业务。

        支持三种处理结论：
        - reship: 补发，自动生成新的送货单
        - rework: 返工，自动生成返工施工单
        - terminate: 终止，取消关联客户订单
        """
        delivery_order = self.get_object()
        result = DeliveryOrderService.resolve_exception(
            delivery_order=delivery_order,
            resolution=request.data.get("resolution"),
            resolution_notes=request.data.get("resolution_notes"),
            user=request.user,
        )
        delivery_order = result.pop("delivery_order")
        serializer = self.get_serializer(delivery_order)
        return APIResponse.success(
            data={"delivery_order": serializer.data, **result},
            message=f"拒收处理已登记：{request.data.get('resolution')}",
        )

    @action(detail=False, methods=["get"])
    @delivery_summary_docs
    def summary(self, request):
        """发货汇总"""
        data = DeliveryOrderService.get_summary(self.get_queryset())
        return APIResponse.success(data=data)


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
    @handle_service_error
    def complete(self, request, pk=None):
        """完成检验"""
        inspection = self.get_object()
        QualityInspectionService.complete(
            inspection=inspection,
            result=request.data.get("result"),
            passed_quantity=request.data.get("passed_quantity", 0),
            failed_quantity=request.data.get("failed_quantity", 0),
        )
        serializer = self.get_serializer(inspection)
        return APIResponse.success(data=serializer.data, message="检验完成")

    @action(detail=False, methods=["get"])
    @quality_summary_docs
    def summary(self, request):
        """质检汇总"""
        data = QualityInspectionService.get_summary(self.get_queryset())
        return APIResponse.success(data=data)
