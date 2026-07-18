"""
物料相关视图集

包含物料、供应商、物料供应商、采购单、收货记录等视图集。
"""

from django.db.models import Case, Count, F, FloatField, Sum, When
from django.utils import timezone
from django_filters import CharFilter, DateFromToRangeFilter, FilterSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, pagination, status
from rest_framework.decorators import action
from workorder.response import APIResponse
from ..services.service_errors import ServiceError
from workorder.docs.materials import (
    material_docs,
    material_supplier_docs,
    materials_low_stock_docs,
    purchase_order_approve_docs,
    purchase_order_cancel_docs,
    purchase_order_docs,
    purchase_order_item_docs,
    purchase_order_pending_inspections_docs,
    purchase_order_place_docs,
    purchase_order_receive_docs,
    purchase_order_receive_records_docs,
    purchase_order_reject_docs,
    purchase_order_submit_docs,
    purchase_receive_record_docs,
    receive_confirm_inspection_docs,
    receive_pending_list_docs,
    receive_pending_return_docs,
    receive_pending_stock_docs,
    receive_return_docs,
    receive_stock_in_docs,
    supplier_docs,
)

from ..models.materials import (
    Material,
    MaterialSupplier,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceiveRecord,
    Supplier,
)
from ..serializers.materials import (
    InspectionConfirmSerializer,
    MaterialSerializer,
    MaterialSupplierSerializer,
    PurchaseOrderDetailSerializer,
    PurchaseOrderItemSerializer,
    PurchaseOrderListSerializer,
    PurchaseReceiveRecordCreateSerializer,
    PurchaseReceiveRecordSerializer,
    ReturnProcessSerializer,
    SupplierSerializer,
)
from ..services.approval_service import ApprovalService
from ..services.purchase_order_flow_service import PurchaseOrderFlowService
from ..services.purchase_order_service import PurchaseOrderService
from ._decorators import handle_service_error
from .base_viewsets import BaseViewSet
from .mixins import ApprovalTimelineMixin
from ..import_export import export_model, import_model
from ..import_export_configs import (
    MATERIAL_EXPORT_CONFIG,
    get_material_import_config,
)


class PurchaseOrderFilterSet(FilterSet):
    supplier_name = CharFilter(
        field_name="supplier__name", lookup_expr="icontains"
    )
    ordered_date = DateFromToRangeFilter()
    expected_date = DateFromToRangeFilter()
    actual_received_date = DateFromToRangeFilter()
    created_at = DateFromToRangeFilter()

    class Meta:
        model = PurchaseOrder
        fields = ["supplier", "status", "approval_status", "work_order"]


@material_docs
class MaterialViewSet(BaseViewSet):
    """物料视图集（优化版）"""

    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    filterset_fields = [
        "default_supplier",
        "need_cutting",
        "is_active",
        "specification_level",
        "material_type",
        "base_material",
        "is_temporary",
    ]
    search_fields = ["name", "code", "specification"]
    ordering_fields = [
        "code",
        "name",
        "unit",
        "unit_price",
        "stock_quantity",
        "created_at",
    ]
    ordering = ["code"]

    def get_queryset(self):
        """优化查询性能"""
        queryset = super().get_queryset()
        include_temporary = self.request.query_params.get("include_temporary", "")
        if include_temporary.lower() not in {"1", "true", "yes"}:
            queryset = queryset.filter(is_temporary=False)
        return queryset.select_related("default_supplier", "base_material")

    @action(detail=False, methods=["get"])
    def export(self, request):
        """导出物料列表 Excel"""
        queryset = self.get_queryset()
        return export_model(queryset, MATERIAL_EXPORT_CONFIG)

    @action(detail=False, methods=["post"])
    def import_materials(self, request):
        """导入物料 Excel"""
        file = request.FILES.get("file")
        if not file:
            return APIResponse.error(
                "未上传文件",
                code=status.HTTP_400_BAD_REQUEST,
            )
        config = get_material_import_config(Material)
        result = import_model(file, config, request.user)
        if result["success_count"] == 0 and result["error_count"] > 0:
            return APIResponse.error(
                f"导入失败: {result['errors'][0] if result['errors'] else '未知错误'}",
                code=status.HTTP_400_BAD_REQUEST,
                data=result,
            )
        created = result.get("created_count", 0)
        updated = result.get("updated_count", 0)
        return APIResponse.success(
            message=(
                f"导入完成: 新增 {created} 条, 更新 {updated} 条, "
                f"失败 {result['error_count']} 条"
            ),
            data=result,
        )


@supplier_docs
class SupplierViewSet(BaseViewSet):
    """供应商视图集（优化版）"""

    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    pagination_class = pagination.PageNumberPagination
    filterset_fields = ["status"]
    search_fields = ["name", "code", "contact_person", "phone", "email"]
    ordering_fields = [
        "created_at",
        "name",
        "code",
        "contact_person",
        "phone",
        "email",
        "status",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        """优化查询性能：使用注解避免N+1查询"""
        queryset = super().get_queryset()
        # 使用注解预计算物料数量
        queryset = queryset.annotate(_material_count=Count("materialsupplier"))
        return queryset


@material_supplier_docs
class MaterialSupplierViewSet(BaseViewSet):
    """物料供应商关联视图集"""

    queryset = MaterialSupplier.objects.all()
    serializer_class = MaterialSupplierSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["material", "supplier", "is_preferred"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


@purchase_order_docs
class PurchaseOrderViewSet(ApprovalTimelineMixin, BaseViewSet):
    """采购单视图集（优化版）"""

    queryset = PurchaseOrder.objects.all()
    search_fields = [
        "order_number",
        "supplier__name",
        "supplier__code",
        "work_order__order_number",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "order_number",
        "supplier__name",
        "status",
        "work_order__order_number",
        "total_amount",
        "items_count",
        "ordered_date",
        "expected_date",
        "actual_received_date",
    ]
    ordering = ["-created_at"]
    filterset_class = PurchaseOrderFilterSet

    def get_serializer_class(self):
        """根据 action 返回不同的序列化器"""
        if self.action == "list":
            return PurchaseOrderListSerializer
        return PurchaseOrderDetailSerializer

    def get_queryset(self):
        """优化查询性能：使用注解避免N+1查询"""
        queryset = super().get_queryset()

        # 优化：预加载关联数据
        queryset = queryset.select_related(
            "supplier", "submitted_by", "approved_by", "work_order"
        ).prefetch_related("items__material")

        # 优化：使用注解计算items_count和received_progress
        queryset = queryset.annotate(
            items_count=Count("items"),
            total_quantity=Sum("items__quantity"),
            total_received=Sum("items__received_quantity"),
        )

        # 计算收货进度百分比
        queryset = queryset.annotate(
            received_progress=Case(
                When(
                    total_quantity__gt=0,
                    then=Sum("items__received_quantity")
                    * 100.0
                    / Sum("items__quantity"),
                ),
                default=0.0,
                output_field=FloatField(),
            )
        )

        return queryset

    # ========== 状态操作 Actions ==========

    @action(detail=True, methods=["post"])
    @purchase_order_submit_docs
    def submit(self, request, pk=None):
        """提交采购单"""
        order = self.get_object()
        if order.approval_status not in ["draft", "rejected"]:
            return APIResponse.error(
                "只有草稿或已拒绝状态的采购单可以提交",
                code=status.HTTP_400_BAD_REQUEST,
            )

        service = ApprovalService(PurchaseOrder)
        try:
            auto_approve = request.data.get("auto_approve", False)
            order = service.submit_for_approval(
                order, request.user, auto_approve=auto_approve
            )
            order.rejection_reason = ""
            order.save(update_fields=["rejection_reason"])
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code)

        return APIResponse.success(message="提交成功")

    @action(detail=True, methods=["post"])
    @purchase_order_approve_docs
    @handle_service_error
    def approve(self, request, pk=None):
        """批准采购单"""
        order = self.get_object()
        if order.approval_status != "submitted":
            return APIResponse.error(
                "只有已提交状态的采购单可以批准",
                code=status.HTTP_400_BAD_REQUEST,
            )

        service = ApprovalService(PurchaseOrder)
        order = service.approve(order, request.user)
        return APIResponse.success(message="批准成功")

    @action(detail=True, methods=["post"])
    @purchase_order_reject_docs
    def reject(self, request, pk=None):
        """拒绝采购单"""
        order = self.get_object()
        if order.approval_status != "submitted":
            return APIResponse.error(
                "只有已提交状态的采购单可以拒绝",
                code=status.HTTP_400_BAD_REQUEST,
            )

        service = ApprovalService(PurchaseOrder)
        try:
            order = service.reject(
                order, request.user, request.data.get("rejection_reason", "")
            )
            order.rejection_reason = request.data.get("rejection_reason", "")
            order.save(update_fields=["rejection_reason"])
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code)

        return APIResponse.success(message="已拒绝，采购单已退回")

    @action(detail=True, methods=["post"])
    @purchase_order_place_docs
    @handle_service_error
    def place_order(self, request, pk=None):
        """下单"""
        order = self.get_object()
        PurchaseOrderFlowService.place_order(
            order=order,
            ordered_date=request.data.get("ordered_date"),
        )
        return APIResponse.success(message="下单成功")

    @action(detail=True, methods=["post"])
    @purchase_order_receive_docs
    def receive(self, request, pk=None):
        """分批收货（改进版）"""
        order = self.get_object()

        serializer = PurchaseReceiveRecordCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                "请求参数错误",
                code=status.HTTP_400_BAD_REQUEST,
                errors=serializer.errors,
            )

        try:
            result = PurchaseOrderService.receive_items(
                order=order,
                items_data=serializer.validated_data.get("items", []),
                received_date=serializer.validated_data.get(
                    "received_date", timezone.now().date()
                ),
                user=request.user,
            )
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code)

        if result["errors"]:
            return APIResponse.success(
                data={
                    "message": "部分收货成功",
                    "created_records": result["created_record_ids"],
                    "errors": result["errors"],
                },
                code=status.HTTP_207_MULTI_STATUS,
            )

        return APIResponse.success(
            data={"created_records": result["created_record_ids"]},
            message="收货成功，请进行质检",
        )

    @action(detail=True, methods=["get"])
    @purchase_order_receive_records_docs
    def receive_records(self, request, pk=None):
        """获取采购单的所有收货记录"""
        order = self.get_object()
        records = (
            PurchaseReceiveRecord.objects.filter(
                purchase_order_item__purchase_order=order
            )
            .select_related(
                "purchase_order_item__material",
                "received_by",
                "inspected_by",
                "stocked_by",
                "returned_by",
            )
            .order_by("-received_date", "-created_at")
        )

        serializer = PurchaseReceiveRecordSerializer(records, many=True)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["get"])
    @purchase_order_pending_inspections_docs
    def pending_inspections(self, request, pk=None):
        """获取待质检的收货记录"""
        order = self.get_object()
        records = (
            PurchaseReceiveRecord.objects.filter(
                purchase_order_item__purchase_order=order,
                inspection_status="pending",
            )
            .select_related("purchase_order_item__material", "received_by")
            .order_by("-received_date")
        )

        serializer = PurchaseReceiveRecordSerializer(records, many=True)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @purchase_order_cancel_docs
    @handle_service_error
    def cancel(self, request, pk=None):
        """取消采购单"""
        order = self.get_object()
        PurchaseOrderService.cancel(order=order)
        return APIResponse.success(message="取消成功")

    @action(detail=False, methods=["post"])
    def create_from_work_order(self, request):
        """从施工单创建采购单"""
        try:
            result = PurchaseOrderService.create_from_work_order(
                work_order_id=request.data.get("work_order_id"),
                material_ids=request.data.get("material_ids"),
                notes=request.data.get("notes", ""),
                item_overrides=request.data.get("items", []),
            )
        except ServiceError as e:
            data = e.data if e.data else {}
            return APIResponse.error(message=str(e), code=e.code, data=data)

        if result["total_count"] == 0:
            return APIResponse.success(
                data=result,
                message="没有可新建采购单的待采购物料",
            )

        return APIResponse.success(
            data=result,
            message=(
                f"成功创建 {result['total_count']} 个采购单，"
                f"包含 {result['created_item_count']} 个物料明细"
            ),
        )

    @action(detail=False, methods=["get"])
    def procurement_summary(self, request):
        """获取采购需求汇总"""
        from workorder.services.procurement_service import ProcurementService

        result = ProcurementService.get_procurement_summary()
        return APIResponse.success(data=result)

    @action(detail=False, methods=["get"])
    def delay_warnings(self, request):
        """获取采购延迟预警"""
        from workorder.services.procurement_service import ProcurementService

        result = ProcurementService.get_delay_warnings()
        return APIResponse.success(data=result)

    @action(detail=False, methods=["get"])
    @materials_low_stock_docs
    def low_stock_materials(self, request):
        """获取库存预警物料"""
        # 查询库存低于最小库存的物料
        materials = (
            Material.objects.filter(stock_quantity__lt=F("min_stock_quantity"))
            .values(
                "id",
                "code",
                "name",
                "stock_quantity",
                "min_stock_quantity",
                "default_supplier__name",
            )
            .annotate(
                needed_quantity=F("min_stock_quantity") - F("stock_quantity")
            )
        )

        return APIResponse.success(data={"materials": list(materials)})


@purchase_order_item_docs
class PurchaseOrderItemViewSet(BaseViewSet):
    """采购单明细视图集"""

    queryset = PurchaseOrderItem.objects.all()
    serializer_class = PurchaseOrderItemSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ["created_at"]
    ordering = ["purchase_order", "id"]

    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class PurchaseOrderItemFilterSet(FilterSet):
            class Meta:
                model = PurchaseOrderItem
                fields = ["purchase_order", "material", "status"]

        return PurchaseOrderItemFilterSet

    def get_queryset(self):
        """优化查询"""
        return (
            super()
            .get_queryset()
            .select_related(
                "purchase_order", "material", "work_order_material"
            )
            .prefetch_related("receive_records")
        )


@purchase_receive_record_docs
class PurchaseReceiveRecordViewSet(BaseViewSet):
    """采购收货记录视图集

    提供收货记录的CRUD操作和质检、入库、退货等业务操作。
    """

    queryset = PurchaseReceiveRecord.objects.all()
    serializer_class = PurchaseReceiveRecordSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = [
        "delivery_note_number",
        "purchase_order_item__material__name",
    ]
    ordering_fields = ["received_date", "created_at"]
    ordering = ["-received_date", "-created_at"]

    def get_filterset(self):
        """延迟创建 FilterSet"""
        from django_filters import CharFilter, FilterSet

        class PurchaseReceiveRecordFilterSet(FilterSet):
            purchase_order = CharFilter(
                field_name="purchase_order_item__purchase_order",
                lookup_expr="exact",
            )

            class Meta:
                model = PurchaseReceiveRecord
                fields = [
                    "purchase_order_item",
                    "inspection_status",
                    "is_stocked",
                    "is_returned",
                ]

        return PurchaseReceiveRecordFilterSet

    def get_queryset(self):
        """优化查询"""
        return (
            super()
            .get_queryset()
            .select_related(
                "purchase_order_item__purchase_order__supplier",
                "purchase_order_item__material",
                "received_by",
                "inspected_by",
                "stocked_by",
                "returned_by",
            )
        )

    @action(detail=True, methods=["post"])
    @receive_confirm_inspection_docs
    def confirm_inspection(self, request, pk=None):
        """确认质检结果

        将收货记录的质检状态从"待质检"更新为具体结果。
        """
        record = self.get_object()

        if record.inspection_status != "pending":
            return APIResponse.error(
                "该记录已完成质检", code=status.HTTP_400_BAD_REQUEST
            )

        serializer = InspectionConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                "请求参数错误",
                code=status.HTTP_400_BAD_REQUEST,
                errors=serializer.errors,
            )

        qualified_qty = serializer.validated_data["qualified_quantity"]
        unqualified_qty = serializer.validated_data.get(
            "unqualified_quantity", 0
        )
        reason = serializer.validated_data.get("unqualified_reason", "")

        # 验证数量总和
        total = qualified_qty + unqualified_qty
        if total != record.received_quantity:
            return APIResponse.error(
                (
                    f"合格数量({qualified_qty}) + 不合格数量({unqualified_qty}) "
                    f"必须等于收货数量({record.received_quantity})"
                ),
                code=status.HTTP_400_BAD_REQUEST,
            )

        # 确认质检
        record.confirm_inspection(
            qualified_qty=qualified_qty,
            unqualified_qty=unqualified_qty,
            reason=reason,
            user=request.user,
        )

        return APIResponse.success(
            data={
                "message": "质检确认成功",
                "inspection_status": record.inspection_status,
                "qualified_quantity": str(record.qualified_quantity),
                "unqualified_quantity": str(record.unqualified_quantity),
            }
        )

    @action(detail=True, methods=["post"])
    @receive_stock_in_docs
    def stock_in(self, request, pk=None):
        """合格物料入库

        将质检合格的物料入库，更新物料库存。
        """
        record = self.get_object()

        if record.inspection_status == "pending":
            return APIResponse.error(
                "请先完成质检", code=status.HTTP_400_BAD_REQUEST
            )

        if record.is_stocked:
            return APIResponse.error(
                "该记录已入库", code=status.HTTP_400_BAD_REQUEST
            )

        if not record.qualified_quantity or record.qualified_quantity <= 0:
            return APIResponse.error(
                "没有合格物料可入库", code=status.HTTP_400_BAD_REQUEST
            )

        success = record.stock_in(user=request.user)

        if success:
            return APIResponse.success(
                data={
                    "message": "入库成功",
                    "stocked_quantity": str(record.qualified_quantity),
                    "material_name": record.material.name,
                    "new_stock": str(record.material.stock_quantity),
                }
            )
        else:
            return APIResponse.error(
                "入库失败", code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"])
    @receive_return_docs
    def process_return(self, request, pk=None):
        """处理退货

        将质检不合格的物料进行退货处理。
        """
        record = self.get_object()

        if record.inspection_status == "pending":
            return APIResponse.error(
                "请先完成质检", code=status.HTTP_400_BAD_REQUEST
            )

        if record.is_returned:
            return APIResponse.error(
                "该记录已退货", code=status.HTTP_400_BAD_REQUEST
            )

        if not record.unqualified_quantity or record.unqualified_quantity <= 0:
            return APIResponse.error(
                "没有不合格物料可退货", code=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReturnProcessSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                "请求参数错误",
                code=status.HTTP_400_BAD_REQUEST,
                errors=serializer.errors,
            )

        return_qty = serializer.validated_data["return_quantity"]
        return_note = serializer.validated_data.get("return_note", "")

        if return_qty > record.unqualified_quantity:
            return APIResponse.error(
                f"退货数量({return_qty})不能超过不合格数量({record.unqualified_quantity})",
                code=status.HTTP_400_BAD_REQUEST,
            )

        success = record.process_return(
            return_qty=return_qty, note=return_note, user=request.user
        )

        if success:
            return APIResponse.success(
                data={
                    "message": "退货处理成功",
                    "returned_quantity": str(return_qty),
                    "material_name": record.material.name,
                }
            )
        else:
            return APIResponse.error(
                "退货处理失败", code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"])
    @receive_pending_list_docs
    def pending_list(self, request):
        """获取所有待质检的收货记录"""
        records = (
            self.get_queryset()
            .filter(inspection_status="pending")
            .order_by("-received_date")
        )

        page = self.paginate_queryset(records)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated = self.get_paginated_response(serializer.data)
            return APIResponse.success(data=paginated.data)

        serializer = self.get_serializer(records, many=True)
        return APIResponse.success(data=serializer.data)

    @action(detail=False, methods=["get"])
    @receive_pending_stock_docs
    def pending_stock_in(self, request):
        """获取待入库的收货记录（已质检但未入库）"""
        records = (
            self.get_queryset()
            .filter(
                inspection_status__in=["qualified", "partial_qualified"],
                is_stocked=False,
                qualified_quantity__gt=0,
            )
            .order_by("-inspected_at")
        )

        page = self.paginate_queryset(records)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated = self.get_paginated_response(serializer.data)
            return APIResponse.success(data=paginated.data)

        serializer = self.get_serializer(records, many=True)
        return APIResponse.success(data=serializer.data)

    @action(detail=False, methods=["get"])
    @receive_pending_return_docs
    def pending_return(self, request):
        """获取待退货的收货记录（有不合格物料但未退货）"""
        records = (
            self.get_queryset()
            .filter(
                inspection_status__in=["unqualified", "partial_qualified"],
                is_returned=False,
                unqualified_quantity__gt=0,
            )
            .order_by("-inspected_at")
        )

        page = self.paginate_queryset(records)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated = self.get_paginated_response(serializer.data)
            return APIResponse.success(data=paginated.data)

        serializer = self.get_serializer(records, many=True)
        return APIResponse.success(data=serializer.data)
