"""
财务相关视图集

包含财务管理的所有视图集：
- CostCenterViewSet: 成本中心
- CostItemViewSet: 成本项目
- ProductionCostViewSet: 生产成本
- InvoiceViewSet: 发票
- PaymentViewSet: 收款记录
- PaymentPlanViewSet: 收款计划
- StatementViewSet: 对账单
"""

from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from workorder.permission_utils import PermissionUtils, apply_data_scope
from workorder.permissions import SuperuserFriendlyModelPermissions
from workorder.response import APIResponse
from workorder.services.finance_service import (
    InvoiceService,
    PaymentPlanService,
    ProductionCostService,
    StatementService,
)
from workorder.services.payment_service import PaymentService
from workorder.services.service_errors import ServiceError
from workorder.services.supplier_payment_service import SupplierPaymentService
from .mixins import ApprovalTimelineMixin
from workorder.docs.finance import (
    cost_center_docs,
    cost_item_docs,
    invoice_approve_docs,
    invoice_docs,
    invoice_submit_docs,
    invoice_summary_docs,
    payment_docs,
    payment_plan_docs,
    payment_plan_update_docs,
    payment_summary_docs,
    production_cost_docs,
    production_cost_material_docs,
    production_cost_stats_docs,
    production_cost_total_docs,
    statement_confirm_docs,
    statement_docs,
    statement_generate_docs,
)

from workorder.models import (
    CostCenter,
    CostItem,
    Invoice,
    Payment,
    PaymentPlan,
    ProductionCost,
    Statement,
    SupplierPayment,
)
from workorder.serializers.finance import (
    CostCenterSerializer,
    CostItemSerializer,
    InvoiceCreateSerializer,
    InvoiceSerializer,
    InvoiceUpdateSerializer,
    PaymentCreateSerializer,
    PaymentPlanSerializer,
    PaymentSerializer,
    PaymentUpdateSerializer,
    ProductionCostSerializer,
    ProductionCostUpdateSerializer,
    StatementCreateSerializer,
    StatementSerializer,
    SupplierPaymentCreateSerializer,
    SupplierPaymentSerializer,
)


def _scope_finance_queryset(
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
        bypass_check=PermissionUtils.is_finance_user,
    )


@cost_center_docs
class CostCenterViewSet(viewsets.ModelViewSet):
    """成本中心视图集"""

    queryset = CostCenter.objects.select_related("manager", "parent").all()
    serializer_class = CostCenterSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = [
        "code",
        "name",
        "type",
        "manager__username",
        "parent__name",
        "is_active",
        "created_at",
        "updated_at",
    ]
    ordering = ["code"]

    def get_queryset(self):
        """支持搜索和过滤"""
        queryset = super().get_queryset()

        center_type = self.request.query_params.get("type")
        if center_type:
            queryset = queryset.filter(type=center_type)

        parent_id = self.request.query_params.get("parent")
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)

        # 只显示启用的成本中心
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == "true")

        # 搜索
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(code__icontains=search)
            )

        return queryset


@cost_item_docs
class CostItemViewSet(viewsets.ModelViewSet):
    """成本项目视图集"""

    queryset = CostItem.objects.all()
    serializer_class = CostItemSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = [
        "code",
        "name",
        "type",
        "allocation_method",
        "is_active",
        "created_at",
        "updated_at",
    ]
    ordering = ["code"]

    def get_queryset(self):
        """支持搜索和过滤"""
        queryset = super().get_queryset()

        # 只显示启用的成本项目
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == "true")

        # 按类型过滤
        cost_type = self.request.query_params.get("type")
        if cost_type:
            queryset = queryset.filter(type=cost_type)

        # 按分摊方法过滤
        allocation_method = self.request.query_params.get("allocation_method")
        if allocation_method:
            queryset = queryset.filter(allocation_method=allocation_method)

        # 搜索
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(code__icontains=search)
            )

        return queryset


@production_cost_docs
class ProductionCostViewSet(viewsets.ModelViewSet):
    """生产成本视图集"""

    queryset = ProductionCost.objects.select_related(
        "work_order", "work_order__customer", "calculated_by"
    ).prefetch_related("work_order__products__product")
    serializer_class = ProductionCostSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = [
        "period",
        "work_order__order_number",
        "work_order__customer__name",
        "material_cost",
        "labor_cost",
        "equipment_cost",
        "overhead_cost",
        "total_cost",
        "standard_cost",
        "variance",
        "variance_rate",
        "calculated_at",
        "created_at",
        "updated_at",
    ]
    ordering = ["-period"]

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = _scope_finance_queryset(
            queryset,
            self.request.user,
            work_order_path="work_order",
            ownership_paths=("calculated_by",),
        )

        period = self.request.query_params.get("period")
        if period:
            queryset = queryset.filter(period=period)

        period_start = self.request.query_params.get("period_start")
        if period_start:
            queryset = queryset.filter(period__gte=period_start)

        period_end = self.request.query_params.get("period_end")
        if period_end:
            queryset = queryset.filter(period__lte=period_end)

        customer = self.request.query_params.get("customer")
        if customer:
            queryset = queryset.filter(work_order__customer_id=customer)

        work_order = self.request.query_params.get("work_order")
        if work_order:
            queryset = queryset.filter(work_order_id=work_order)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(work_order__order_number__icontains=search)
                | Q(work_order__customer__name__icontains=search)
                | Q(period__icontains=search)
                | Q(notes__icontains=search)
            )

        return queryset

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action in ["update", "partial_update"]:
            return ProductionCostUpdateSerializer
        return ProductionCostSerializer

    @action(detail=True, methods=["post"])
    @production_cost_material_docs
    def calculate_material(self, request, pk=None):
        """自动计算材料成本"""
        cost = self.get_object()

        try:
            ProductionCostService.calculate_material(cost)
            serializer = self.get_serializer(cost)
            return APIResponse.success(data=serializer.data, message="材料成本计算成功")
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code, data=e.data)

    @action(detail=True, methods=["post"])
    @production_cost_total_docs
    def calculate_total(self, request, pk=None):
        """计算总成本和差异"""
        cost = self.get_object()

        try:
            ProductionCostService.calculate_total(cost)
            serializer = self.get_serializer(cost)
            return APIResponse.success(data=serializer.data, message="总成本计算成功")
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code, data=e.data)

    @action(detail=False, methods=["get"])
    @production_cost_stats_docs
    def stats(self, request):
        """成本统计"""
        period = request.query_params.get("period")
        data = ProductionCostService.get_stats(self.get_queryset(), period=period)
        return APIResponse.success(data=data)


@invoice_docs
class InvoiceViewSet(ApprovalTimelineMixin, viewsets.ModelViewSet):
    """发票视图集"""

    queryset = (
        Invoice.objects.select_related(
            "customer",
            "sales_order",
            "work_order",
            "created_by",
            "submitted_by",
            "approved_by",
        )
        .annotate(
            received_payment_amount=Coalesce(
                Sum("payments__applied_amount"),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .all()
    )
    serializer_class = InvoiceSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = [
        "invoice_number",
        "invoice_code",
        "invoice_type",
        "customer__name",
        "amount",
        "tax_amount",
        "total_amount",
        "issue_date",
        "status",
        "created_at",
        "updated_at",
        "received_payment_amount",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action == "create":
            return InvoiceCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return InvoiceUpdateSerializer
        return InvoiceSerializer

    def get_queryset(self):
        """支持过滤和搜索"""
        queryset = super().get_queryset()
        queryset = _scope_finance_queryset(
            queryset,
            self.request.user,
            customer_path="customer",
            sales_order_path="sales_order",
            work_order_path="work_order",
            ownership_paths=("created_by", "submitted_by", "approved_by"),
        )

        # 按状态过滤
        invoice_status = self.request.query_params.get("status")
        if invoice_status:
            queryset = queryset.filter(status=invoice_status)
            
        approval_status = self.request.query_params.get("approval_status")
        if approval_status:
            queryset = queryset.filter(approval_status=approval_status)

        todo_filter = (self.request.query_params.get("todo") or "").strip()
        if todo_filter == "pending_attachment":
            queryset = queryset.filter(
                status__in=["issued", "sent", "received"]
            ).filter(Q(attachment="") | Q(attachment__isnull=True))
        elif todo_filter == "pending_receipt":
            queryset = queryset.filter(status__in=["issued", "sent"])
        elif todo_filter == "pending_payment":
            queryset = queryset.filter(
                status__in=["issued", "sent", "received"],
                received_payment_amount__lt=F("total_amount"),
            )

        # 按客户过滤
        customer_id = self.request.query_params.get("customer")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # 按日期范围过滤
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(issue_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(issue_date__lte=end_date)

        # 搜索
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search)
                | Q(customer__name__icontains=search)
            )

        return queryset

    @action(detail=True, methods=["post"])
    @invoice_submit_docs
    def submit(self, request, pk=None):
        """提交发票"""
        invoice = self.get_object()

        try:
            InvoiceService.submit(
                invoice=invoice,
                user=request.user,
                auto_approve=request.data.get("auto_approve", False),
            )
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code)

        serializer = self.get_serializer(invoice)
        return APIResponse.success(data=serializer.data, message="发票提交成功")

    @action(detail=True, methods=["post"])
    @invoice_approve_docs
    def approve(self, request, pk=None):
        """审核发票"""
        invoice = self.get_object()

        try:
            InvoiceService.approve(
                invoice=invoice,
                user=request.user,
                approved=request.data.get("approved", True),
                approval_comment=request.data.get("approval_comment", ""),
            )
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code)

        serializer = self.get_serializer(invoice)
        return APIResponse.success(data=serializer.data, message="发票审核成功")

    @action(detail=False, methods=["get"])
    @invoice_summary_docs
    def summary(self, request):
        """发票汇总"""
        data = InvoiceService.get_summary(self.get_queryset())
        return APIResponse.success(data=data)


@payment_docs
class PaymentViewSet(viewsets.ModelViewSet):
    """收款记录视图集"""

    queryset = Payment.objects.select_related(
        "customer", "sales_order", "invoice", "recorded_by"
    ).all()
    serializer_class = PaymentSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = [
        "payment_number",
        "customer__name",
        "sales_order__order_number",
        "invoice__invoice_number",
        "amount",
        "applied_amount",
        "remaining_amount",
        "payment_method",
        "payment_date",
        "created_at",
    ]
    ordering = ["-payment_date"]

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action == "create":
            return PaymentCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return PaymentUpdateSerializer
        return PaymentSerializer

    def perform_create(self, serializer):
        """创建收款记录后回写订单付款状态"""
        payment = serializer.save(recorded_by=self.request.user)
        from workorder.services.payment_service import PaymentService
        PaymentService.apply_payment(payment=payment, user=self.request.user)

    def perform_update(self, serializer):
        """更新收款记录后回写订单付款状态"""
        payment = serializer.save()
        from workorder.services.payment_service import PaymentService
        PaymentService.apply_payment(payment=payment, user=self.request.user)

    def perform_destroy(self, instance):
        """删除收款记录后重新计算关联订单付款状态"""
        sales_order = instance.sales_order
        super().perform_destroy(instance)
        if sales_order:
            from workorder.services.payment_service import PaymentService

            PaymentService._update_sales_order_payment_status(sales_order)
            PaymentService._distribute_to_plans(sales_order)

    def get_queryset(self):
        """支持过滤和搜索"""
        queryset = super().get_queryset()
        queryset = _scope_finance_queryset(
            queryset,
            self.request.user,
            customer_path="customer",
            sales_order_path="sales_order",
            ownership_paths=("recorded_by",),
        )

        # 按客户过滤
        customer_id = self.request.query_params.get("customer")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        todo_filter = (self.request.query_params.get("todo") or "").strip()
        if todo_filter == "pending_writeoff":
            queryset = queryset.filter(remaining_amount__gt=0)
        elif todo_filter == "missing_invoice_link":
            queryset = queryset.filter(invoice__isnull=True, sales_order__isnull=False)

        # 按收款方式过滤
        payment_method = self.request.query_params.get("payment_method")
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        # 按日期范围过滤
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(payment_date__lte=end_date)

        # 搜索
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(payment_number__icontains=search)
                | Q(customer__name__icontains=search)
            )

        return queryset

    @action(detail=False, methods=["get"])
    @payment_summary_docs
    def summary(self, request):
        """收款汇总"""
        data = PaymentService.get_summary(self.get_queryset())
        return APIResponse.success(data=data)


@payment_plan_docs
class PaymentPlanViewSet(viewsets.ModelViewSet):
    """收款计划视图集"""

    queryset = PaymentPlan.objects.select_related("sales_order").all()
    serializer_class = PaymentPlanSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = [
        "sales_order__order_number",
        "sales_order__customer__name",
        "plan_amount",
        "paid_amount",
        "plan_date",
        "status",
        "created_at",
    ]
    ordering = ["plan_date"]

    def get_queryset(self):
        """支持过滤"""
        queryset = super().get_queryset()
        queryset = _scope_finance_queryset(
            queryset,
            self.request.user,
            sales_order_path="sales_order",
        )

        # 按状态过滤
        plan_status = self.request.query_params.get("status")
        if plan_status:
            queryset = queryset.filter(status=plan_status)

        todo_filter = (self.request.query_params.get("todo") or "").strip()
        today = timezone.localdate()
        if todo_filter == "overdue":
            queryset = queryset.filter(plan_date__lt=today).exclude(status="completed")
        elif todo_filter == "due_today":
            queryset = queryset.filter(plan_date=today).exclude(status="completed")

        # 按日期范围过滤
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(plan_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(plan_date__lte=end_date)

        search = (self.request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(sales_order__order_number__icontains=search)
                | Q(sales_order__customer__name__icontains=search)
                | Q(plan_date__icontains=search)
            )

        return queryset

    @action(detail=True, methods=["post"])
    @payment_plan_update_docs
    def update_status(self, request, pk=None):
        """更新收款状态"""
        plan = self.get_object()
        plan.update_status()

        serializer = self.get_serializer(plan)
        return APIResponse.success(data=serializer.data, message="状态更新成功")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """收款计划汇总"""
        data = PaymentPlanService.get_summary(self.get_queryset())
        return APIResponse.success(data=data)


@statement_docs
class StatementViewSet(viewsets.ModelViewSet):
    """对账单视图集"""

    queryset = Statement.objects.select_related(
        "customer", "supplier", "created_by", "confirmed_by"
    ).all()
    serializer_class = StatementSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = [
        "statement_number",
        "statement_type",
        "customer__name",
        "supplier__name",
        "period",
        "start_date",
        "end_date",
        "opening_balance",
        "total_debit",
        "total_credit",
        "closing_balance",
        "status",
        "created_at",
        "confirmed_at",
    ]
    ordering = ["-period"]

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action == "create":
            return StatementCreateSerializer
        return StatementSerializer

    def get_queryset(self):
        """支持过滤和搜索"""
        queryset = super().get_queryset()
        queryset = _scope_finance_queryset(
            queryset,
            self.request.user,
            customer_path="customer",
            ownership_paths=("created_by", "confirmed_by"),
        )

        # 按对账单类型过滤
        statement_type = self.request.query_params.get("type")
        if statement_type:
            queryset = queryset.filter(statement_type=statement_type)

        # 按状态过滤
        statement_status = self.request.query_params.get("status")
        if statement_status:
            queryset = queryset.filter(status=statement_status)

        todo_filter = (self.request.query_params.get("todo") or "").strip()
        if todo_filter == "pending_confirm":
            queryset = queryset.filter(status__in=["draft", "sent"])
        elif todo_filter == "disputed":
            queryset = queryset.filter(status="disputed")

        # 按客户过滤
        customer_id = self.request.query_params.get("customer")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # 按供应商过滤
        supplier_id = self.request.query_params.get("supplier")
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)

        # 按期间范围过滤
        period_start = self.request.query_params.get("period_start")
        period_end = self.request.query_params.get("period_end")
        if period_start:
            queryset = queryset.filter(start_date__gte=period_start)
        if period_end:
            queryset = queryset.filter(end_date__lte=period_end)

        # 搜索
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(statement_number__icontains=search)
                | Q(period__icontains=search)
                | Q(customer__name__icontains=search)
                | Q(supplier__name__icontains=search)
            )

        return queryset

    @action(detail=True, methods=["post"])
    @statement_confirm_docs
    def confirm(self, request, pk=None):
        """确认对账单"""
        statement = self.get_object()

        try:
            StatementService.confirm(
                statement=statement,
                user=request.user,
                confirmed=request.data.get("confirmed", True),
                confirmation_notes=request.data.get("confirm_notes")
                or request.data.get("confirmation_notes"),
            )
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code, data=e.data)

        serializer = self.get_serializer(statement)
        return APIResponse.success(data=serializer.data, message="对账单确认成功")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """对账单汇总"""
        data = StatementService.get_summary(self.get_queryset())
        return APIResponse.success(data=data)

    @action(detail=False, methods=["get"])
    @statement_generate_docs
    def generate(self, request):
        """生成对账单"""
        try:
            data = StatementService.generate(
                customer_id=request.query_params.get("customer"),
                supplier_id=request.query_params.get("supplier"),
                period=request.query_params.get("period"),
            )
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code, data=e.data)

        return APIResponse.success(data=data)


class SupplierPaymentViewSet(viewsets.ModelViewSet):
    """供应商付款视图集"""

    queryset = SupplierPayment.objects.select_related(
        "purchase_order", "supplier", "created_by", "submitted_by", "approved_by"
    ).all()
    serializer_class = SupplierPaymentSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "supplier", "purchase_order", "payment_date"]
    ordering_fields = ["payment_date", "amount", "created_at"]
    ordering = ["-payment_date"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SupplierPaymentCreateSerializer
        return SupplierPaymentSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """提交付款审核"""
        payment = self.get_object()
        try:
            SupplierPaymentService.submit(payment=payment, user=request.user)
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code, data=e.data)
        return APIResponse.success(data=SupplierPaymentSerializer(payment).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """审核通过付款"""
        payment = self.get_object()
        try:
            SupplierPaymentService.approve(payment=payment, user=request.user)
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code, data=e.data)
        return APIResponse.success(data=SupplierPaymentSerializer(payment).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """拒绝付款"""
        payment = self.get_object()
        try:
            SupplierPaymentService.reject(
                payment=payment,
                user=request.user,
                approval_comment=request.data.get("approval_comment", ""),
            )
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code, data=e.data)
        return APIResponse.success(data=SupplierPaymentSerializer(payment).data)
