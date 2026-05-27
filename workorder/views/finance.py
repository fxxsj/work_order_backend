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

from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from workorder.permission_utils import PermissionUtils, apply_data_scope
from workorder.permissions import SuperuserFriendlyModelPermissions
from workorder.response import APIResponse
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

    queryset = CostCenter.objects.all()
    serializer_class = CostCenterSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]

    def get_queryset(self):
        """支持搜索和过滤"""
        queryset = super().get_queryset()

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
            cost.auto_calculate_material_cost()
            serializer = self.get_serializer(cost)
            return APIResponse.success(data=serializer.data, message="材料成本计算成功")
        except Exception as e:
            return APIResponse.error(
                f"计算失败: {str(e)}",
                code=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"])
    @production_cost_total_docs
    def calculate_total(self, request, pk=None):
        """计算总成本和差异"""
        cost = self.get_object()

        try:
            cost.calculate_total_cost()
            serializer = self.get_serializer(cost)
            return APIResponse.success(data=serializer.data, message="总成本计算成功")
        except Exception as e:
            return APIResponse.error(
                f"计算失败: {str(e)}",
                code=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    @production_cost_stats_docs
    def stats(self, request):
        """成本统计"""
        # 获取查询参数
        period = request.query_params.get("period")

        queryset = self.get_queryset()
        if period:
            queryset = queryset.filter(period=period)

        # 统计数据
        stats = queryset.aggregate(
            total_orders=Count("work_order"),
            total_cost=Sum("total_cost"),
            total_material=Sum("material_cost"),
            total_labor=Sum("labor_cost"),
            total_equipment=Sum("equipment_cost"),
            total_overhead=Sum("overhead_cost"),
            total_variance=Sum("variance"),
        )

        return APIResponse.success(data=stats)


@invoice_docs
class InvoiceViewSet(viewsets.ModelViewSet):
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
                Sum("payments__amount"),
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

        if invoice.status != "draft":
            return APIResponse.error(
                "只有草稿状态的发票可以提交", code=status.HTTP_400_BAD_REQUEST
            )

        invoice.status = "issued"
        invoice.submitted_by = request.user
        invoice.submitted_at = timezone.now()
        invoice.save()

        serializer = self.get_serializer(invoice)
        return APIResponse.success(data=serializer.data, message="发票提交成功")

    @action(detail=True, methods=["post"])
    @invoice_approve_docs
    def approve(self, request, pk=None):
        """审核发票"""
        invoice = self.get_object()

        if invoice.status != "issued":
            return APIResponse.error(
                "只有已开具状态的发票可以审核", code=status.HTTP_400_BAD_REQUEST
            )

        # 获取审核意见
        approval_comment = request.data.get("approval_comment")
        approved = request.data.get("approved", True)

        if approved:
            invoice.status = "received"
            invoice.approved_by = request.user
            invoice.approved_at = timezone.now()
        else:
            invoice.status = "cancelled"
            if approval_comment:
                invoice.notes = (
                    f"{invoice.notes}\n审核意见: {approval_comment}"
                    if invoice.notes
                    else f"审核意见: {approval_comment}"
                )

        invoice.save()

        serializer = self.get_serializer(invoice)
        return APIResponse.success(data=serializer.data, message="发票审核成功")

    @action(detail=False, methods=["get"])
    @invoice_summary_docs
    def summary(self, request):
        """发票汇总"""
        queryset = self.get_queryset()
        actionable_statuses = ["issued", "sent", "received"]
        pending_payment_queryset = queryset.filter(
            status__in=actionable_statuses,
            received_payment_amount__lt=F("total_amount"),
        )

        # 统计数据
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
            pending_receipt_count=Count("id", filter=Q(status__in=["issued", "sent"])),
        )
        
        # 兜底空值
        summary["total_amount"] = summary["total_amount"] or Decimal("0")
        summary["tax_amount"] = summary["tax_amount"] or Decimal("0")
        
        # 由于 received_payment_amount 是一个聚合字段，Django 不允许直接在 aggregate 中对其使用 filter (嵌套聚合)
        # 所以我们单独计算 pending_payment_count
        summary["pending_payment_count"] = pending_payment_queryset.count()

        pending_payment_amount = Decimal("0")
        for _, total_amount, received_amount in pending_payment_queryset.values_list(
            "id", "total_amount", "received_payment_amount"
        ):
            gap = (total_amount or Decimal("0")) - (received_amount or Decimal("0"))
            if gap > 0:
                pending_payment_amount += gap
        summary["pending_payment_amount"] = pending_payment_amount

        # 按状态统计
        status_stats = (
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )

        return APIResponse.success(
            data={"summary": summary, "by_status": list(status_stats)}
        )


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
        queryset = self.get_queryset()

        # 统计数据
        summary = queryset.aggregate(
            total_count=Count("id"),
            total_amount=Sum("amount"),
            applied_amount=Sum("applied_amount"),
            remaining_amount=Sum("remaining_amount"),
            missing_invoice_link_count=Count(
                "id", filter=Q(invoice__isnull=True) & Q(sales_order__isnull=False)
            ),
        )
        
        # 兜底空值
        summary["total_amount"] = summary["total_amount"] or Decimal("0")
        summary["applied_amount"] = summary["applied_amount"] or Decimal("0")
        summary["remaining_amount"] = summary["remaining_amount"] or Decimal("0")
        
        summary["pending_writeoff_count"] = queryset.filter(remaining_amount__gt=0).count()
        summary["pending_writeoff_amount"] = queryset.filter(
            remaining_amount__gt=0
        ).aggregate(total=Sum("remaining_amount"))["total"] or Decimal("0")

        # 按收款方式统计
        method_stats = (
            queryset.values("payment_method")
            .annotate(count=Count("id"), total=Sum("amount"))
            .order_by("payment_method")
        )

        return APIResponse.success(
            data={"summary": summary, "by_method": list(method_stats)}
        )


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
        queryset = self.get_queryset()
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
        for plan_amount, paid_amount, plan_date, plan_status in queryset.values_list(
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
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )
        return APIResponse.success(
            data={"summary": summary, "by_status": list(by_status)}
        )


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

        # 按对账单类型过滤（兼容前端参数 statement_type 和后端参数 type）
        statement_type = self.request.query_params.get(
            "statement_type"
        ) or self.request.query_params.get("type")
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

        # 按客户过滤（兼容前端参数 partner 和后端参数 customer）
        customer_id = self.request.query_params.get(
            "partner"
        ) or self.request.query_params.get("customer")
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

        if statement.status not in ["draft", "sent"]:
            return APIResponse.error(
                "只有草稿或已发送状态的对账单可以确认", code=status.HTTP_400_BAD_REQUEST
            )

        # 获取确认信息
        confirmed = request.data.get("confirmed", True)
        confirmation_notes = request.data.get("confirm_notes") or request.data.get(
            "confirmation_notes"
        )

        statement.confirmed_by = request.user
        statement.confirmed_at = timezone.now()
        statement.confirmation_notes = confirmation_notes

        if confirmed:
            statement.status = "confirmed"
        else:
            statement.status = "disputed"

        statement.save()

        serializer = self.get_serializer(statement)
        return APIResponse.success(data=serializer.data, message="对账单确认成功")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """对账单汇总"""
        queryset = self.get_queryset()
        summary = queryset.aggregate(
            total_count=Count("id"),
            pending_confirm_count=Count("id", filter=Q(status__in=["draft", "sent"])),
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
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )
        return APIResponse.success(
            data={"summary": summary, "by_status": list(by_status)}
        )

    @action(detail=False, methods=["get"])
    @statement_generate_docs
    def generate(self, request):
        """生成对账单"""
        # 获取参数
        customer_id = request.query_params.get("customer")
        supplier_id = request.query_params.get("supplier")
        period = request.query_params.get("period")

        if not period:
            return APIResponse.error(
                "必须指定对账周期", code=status.HTTP_400_BAD_REQUEST
            )

        # 解析周期 (格式: 2024-01)
        try:
            year, month = period.split("-")
            from calendar import monthrange
            from datetime import date

            start_date = date(int(year), int(month), 1)
            last_day = monthrange(int(year), int(month))[1]
            end_date = date(int(year), int(month), last_day)
        except Exception:
            return APIResponse.error(
                "周期格式错误，应为 YYYY-MM", code=status.HTTP_400_BAD_REQUEST
            )

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

            from workorder.models import SalesOrder

            orders = (
                SalesOrder.objects.filter(
                    customer_id=customer_id,
                    order_date__gte=start_date,
                    order_date__lte=end_date,
                )
                .exclude(status__in=["draft", "rejected", "cancelled"])
                .only("total_amount")
            )
            total_debit = orders.aggregate(total=Sum("total_amount"))["total"] or 0

            payments = Payment.objects.filter(
                customer_id=customer_id,
                payment_date__gte=start_date,
                payment_date__lte=end_date,
            ).only("amount")
            total_credit = payments.aggregate(total=Sum("amount"))["total"] or 0

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
                purchase_orders.aggregate(total=Sum("total_amount"))["total"] or 0
            )

            # NOTE: 当前系统未建模“供应商付款”记录，本期贷方暂不计算。
            total_credit = 0
        else:
            return APIResponse.error(
                "必须指定客户或供应商", code=status.HTTP_400_BAD_REQUEST
            )

        closing_balance = opening_balance + total_debit - total_credit

        return APIResponse.success(
            data={
                "statement_type": statement_type,
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "opening_balance": opening_balance,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "closing_balance": closing_balance,
            }
        )
