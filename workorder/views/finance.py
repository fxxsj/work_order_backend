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

from django.db.models import Count, DecimalField, F, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from workorder.response import APIResponse

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


class CostCenterViewSet(viewsets.ModelViewSet):
    """成本中心视图集"""

    queryset = CostCenter.objects.all()
    serializer_class = CostCenterSerializer

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


class CostItemViewSet(viewsets.ModelViewSet):
    """成本项目视图集"""

    queryset = CostItem.objects.all()
    serializer_class = CostItemSerializer

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


class ProductionCostViewSet(viewsets.ModelViewSet):
    """生产成本视图集"""

    queryset = ProductionCost.objects.select_related(
        "work_order", "calculated_by"
    ).all()
    serializer_class = ProductionCostSerializer

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action in ["update", "partial_update"]:
            return ProductionCostUpdateSerializer
        return ProductionCostSerializer

    @action(detail=True, methods=["post"])
    def calculate_material(self, request, pk=None):
        """自动计算材料成本"""
        cost = self.get_object()

        try:
            cost.auto_calculate_material_cost()
            serializer = self.get_serializer(cost)
            return APIResponse.success(data={"message": "材料成本计算成功", "data": serializer.data})
        except Exception as e:
            return APIResponse.error(
                f"计算失败: {str(e)}",
                code=status.HTTP_400_BAD_REQUEST,
                data={"error": f"计算失败: {str(e)}"},
            )

    @action(detail=True, methods=["post"])
    def calculate_total(self, request, pk=None):
        """计算总成本和差异"""
        cost = self.get_object()

        try:
            cost.calculate_total_cost()
            serializer = self.get_serializer(cost)
            return APIResponse.success(data={"message": "总成本计算成功", "data": serializer.data})
        except Exception as e:
            return APIResponse.error(
                f"计算失败: {str(e)}",
                code=status.HTTP_400_BAD_REQUEST,
                data={"error": f"计算失败: {str(e)}"},
            )

    @action(detail=False, methods=["get"])
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


class InvoiceViewSet(viewsets.ModelViewSet):
    """发票视图集"""

    queryset = Invoice.objects.select_related(
        "customer",
        "sales_order",
        "work_order",
        "created_by",
        "submitted_by",
        "approved_by",
    ).all()
    serializer_class = InvoiceSerializer

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

        # 按状态过滤
        invoice_status = self.request.query_params.get("status")
        if invoice_status:
            queryset = queryset.filter(status=invoice_status)

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
    def submit(self, request, pk=None):
        """提交发票"""
        invoice = self.get_object()

        if invoice.status != "draft":
            return APIResponse.error("只有草稿状态的发票可以提交", code=status.HTTP_400_BAD_REQUEST, data={"error": "只有草稿状态的发票可以提交"})

        invoice.status = "issued"
        invoice.submitted_by = request.user
        invoice.submitted_at = timezone.now()
        invoice.save()

        serializer = self.get_serializer(invoice)
        return APIResponse.success(data={"message": "发票提交成功", "data": serializer.data})

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """审核发票"""
        invoice = self.get_object()

        if invoice.status != "issued":
            return APIResponse.error("只有已开具状态的发票可以审核", code=status.HTTP_400_BAD_REQUEST, data={"error": "只有已开具状态的发票可以审核"})

        # 获取审核意见
        approval_comment = request.data.get("approval_comment")
        approved = request.data.get("approved", True)

        if approved:
            invoice.status = "received"
            invoice.approved_by = request.user
            invoice.approved_at = timezone.now()
        else:
            invoice.status = "cancelled"
            invoice.approval_comment = approval_comment

        invoice.save()

        serializer = self.get_serializer(invoice)
        return APIResponse.success(data={"message": "发票审核成功", "data": serializer.data})

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """发票汇总"""
        queryset = self.get_queryset()

        # 统计数据
        summary = queryset.aggregate(
            total_count=Count("id"),
            total_amount=Sum("total_amount"),
            tax_amount=Sum("tax_amount"),
        )

        # 按状态统计
        status_stats = (
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )

        return APIResponse.success(data={"summary": summary, "by_status": list(status_stats)})


class PaymentViewSet(viewsets.ModelViewSet):
    """收款记录视图集"""

    queryset = Payment.objects.select_related(
        "customer", "sales_order", "invoice", "recorded_by"
    ).all()
    serializer_class = PaymentSerializer

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

        # 按客户过滤
        customer_id = self.request.query_params.get("customer")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

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
    def summary(self, request):
        """收款汇总"""
        queryset = self.get_queryset()

        # 统计数据
        summary = queryset.aggregate(
            total_count=Count("id"),
            total_amount=Sum("amount"),
            applied_amount=Sum("applied_amount"),
            remaining_amount=Sum("remaining_amount"),
        )

        # 按收款方式统计
        method_stats = (
            queryset.values("payment_method")
            .annotate(count=Count("id"), total=Sum("amount"))
            .order_by("payment_method")
        )

        return APIResponse.success(data={"summary": summary, "by_method": list(method_stats)})


class PaymentPlanViewSet(viewsets.ModelViewSet):
    """收款计划视图集"""

    queryset = PaymentPlan.objects.select_related("sales_order").all()
    serializer_class = PaymentPlanSerializer

    def get_queryset(self):
        """支持过滤"""
        queryset = super().get_queryset()

        # 按状态过滤
        plan_status = self.request.query_params.get("status")
        if plan_status:
            queryset = queryset.filter(status=plan_status)

        # 按日期范围过滤
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(plan_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(plan_date__lte=end_date)

        return queryset

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        """更新收款状态"""
        plan = self.get_object()
        plan.update_status()

        serializer = self.get_serializer(plan)
        return APIResponse.success(data={"message": "状态更新成功", "data": serializer.data})


class StatementViewSet(viewsets.ModelViewSet):
    """对账单视图集"""

    queryset = Statement.objects.select_related(
        "customer", "supplier", "created_by", "confirmed_by"
    ).all()
    serializer_class = StatementSerializer

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action == "create":
            return StatementCreateSerializer
        return StatementSerializer

    def get_queryset(self):
        """支持过滤和搜索"""
        queryset = super().get_queryset()

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
                Q(statement_number__icontains=search) | Q(period__icontains=search)
            )

        return queryset

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """确认对账单"""
        statement = self.get_object()

        if statement.status not in ["draft", "sent"]:
            return APIResponse.error("只有草稿或已发送状态的对账单可以确认", code=status.HTTP_400_BAD_REQUEST, data={"error": "只有草稿或已发送状态的对账单可以确认"})

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
        return APIResponse.success(data={"message": "对账单确认成功", "data": serializer.data})

    @action(detail=False, methods=["get"])
    def generate(self, request):
        """生成对账单"""
        # 获取参数
        customer_id = request.query_params.get("customer")
        supplier_id = request.query_params.get("supplier")
        period = request.query_params.get("period")

        if not period:
            return APIResponse.error("必须指定对账周期", code=status.HTTP_400_BAD_REQUEST, data={"error": "必须指定对账周期"})

        # 解析周期 (格式: 2024-01)
        try:
            year, month = period.split("-")
            from calendar import monthrange
            from datetime import date

            start_date = date(int(year), int(month), 1)
            last_day = monthrange(int(year), int(month))[1]
            end_date = date(int(year), int(month), last_day)
        except:
            return APIResponse.error("周期格式错误，应为 YYYY-MM", code=status.HTTP_400_BAD_REQUEST, data={"error": "周期格式错误，应为 YYYY-MM"})

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
            return APIResponse.error("必须指定客户或供应商", code=status.HTTP_400_BAD_REQUEST, data={"error": "必须指定客户或供应商"})

        closing_balance = opening_balance + total_debit - total_credit

        return APIResponse.success(data={
                "statement_type": statement_type,
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "opening_balance": opening_balance,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "closing_balance": closing_balance,
            })
