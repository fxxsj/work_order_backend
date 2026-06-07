"""
财务相关序列化器

包含财务管理的所有序列化器：
- CostCenter: 成本中心
- CostItem: 成本项目
- ProductionCost: 生产成本
- Invoice: 发票
- Payment: 收款记录
- PaymentPlan: 收款计划
- Statement: 对账单
"""

from decimal import Decimal
from typing import Optional

from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from workorder.models import (
    CostCenter,
    CostItem,
    Invoice,
    Payment,
    PaymentPlan,
    ProductionCost,
    Statement,
)

# ==================== 成本核算序列化器 ====================


class CostCenterSerializer(serializers.ModelSerializer):
    """成本中心序列化器"""

    parent_name = serializers.CharField(
        source="parent.name", read_only=True, allow_null=True
    )
    manager_name = serializers.CharField(
        source="manager.username", read_only=True, allow_null=True
    )
    children_count = serializers.SerializerMethodField()
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = CostCenter
        fields = "__all__"

    def validate(self, data):
        """验证成本中心数据"""
        code = data.get("code")
        if code is not None:
            code = code.strip()
            if len(code) < 2 or len(code) > 50:
                raise serializers.ValidationError(
                    {"code": "成本中心编码长度必须为 2-50 个字符"}
                )
            data["code"] = code
        name = data.get("name")
        if name is not None:
            name = name.strip()
            if len(name) < 2 or len(name) > 100:
                raise serializers.ValidationError(
                    {"name": "成本中心名称长度必须为 2-100 个字符"}
                )
            data["name"] = name
        description = data.get("description")
        if description is not None:
            data["description"] = description.strip()
        parent = data.get("parent")
        if self.instance is not None and parent is not None:
            if parent.pk == self.instance.pk:
                raise serializers.ValidationError({"parent": "上级成本中心不能是自身"})
        return data

    def get_children_count(self, obj) -> int:
        """获取子成本中心数量"""
        return obj.children.count() if hasattr(obj, "children") else 0


class CostItemSerializer(serializers.ModelSerializer):
    """成本项目序列化器"""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    allocation_method_display = serializers.CharField(
        source="get_allocation_method_display", read_only=True
    )

    class Meta:
        model = CostItem
        fields = "__all__"

    def validate(self, data):
        """验证成本项目数据"""
        code = data.get("code")
        if code is not None:
            code = code.strip()
            if len(code) < 2 or len(code) > 50:
                raise serializers.ValidationError(
                    {"code": "成本项目编码长度必须为 2-50 个字符"}
                )
            data["code"] = code

        name = data.get("name")
        if name is not None:
            name = name.strip()
            if len(name) < 2 or len(name) > 100:
                raise serializers.ValidationError(
                    {"name": "成本项目名称长度必须为 2-100 个字符"}
                )
            data["name"] = name

        description = data.get("description")
        if description is not None:
            data["description"] = description.strip()

        return data


class ProductionCostSerializer(serializers.ModelSerializer):
    """生产成本序列化器"""

    work_order_number = serializers.CharField(
        source="work_order.order_number", read_only=True
    )
    customer_name = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    calculated_by_name = serializers.CharField(
        source="calculated_by.username", read_only=True, allow_null=True
    )
    variance_rate_formatted = serializers.SerializerMethodField()
    actual_cost = serializers.DecimalField(
        source="total_cost", max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = ProductionCost
        fields = "__all__"
        read_only_fields = ["work_order"]

    def get_customer_name(self, obj) -> Optional[str]:
        """获取客户名称"""
        if obj.work_order and obj.work_order.customer:
            return obj.work_order.customer.name
        return None

    def get_product_name(self, obj) -> Optional[str]:
        """获取施工单产品摘要"""
        if not obj.work_order:
            return None
        products = obj.work_order.products.select_related("product").all()
        if not products:
            return None
        first = products[0]
        first_name = first.product.name if first.product_id else None
        if products.count() > 1 and first_name:
            return f"{first_name} 等{products.count()}款"
        return first_name

    def get_variance_rate_formatted(self, obj) -> str:
        """格式化差异率显示"""
        return f"{obj.variance_rate:.2f}%"


class ProductionCostUpdateSerializer(serializers.ModelSerializer):
    """生产成本更新序列化器"""

    class Meta:
        model = ProductionCost
        fields = [
            "material_cost",
            "labor_cost",
            "equipment_cost",
            "overhead_cost",
            "standard_cost",
            "notes",
        ]


# ==================== 发票管理序列化器 ====================


class InvoiceSerializer(serializers.ModelSerializer):
    """发票序列化器"""

    invoice_type_display = serializers.CharField(
        source="get_invoice_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    approval_status_display = serializers.CharField(
        source="get_approval_status_display", read_only=True
    )

    # 关联信息
    sales_order_number = serializers.CharField(
        source="sales_order.order_number", read_only=True, allow_null=True
    )
    work_order_number = serializers.CharField(
        source="work_order.order_number", read_only=True, allow_null=True
    )
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    # 操作人信息
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, allow_null=True
    )
    submitted_by_name = serializers.CharField(
        source="submitted_by.username", read_only=True, allow_null=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, allow_null=True
    )
    payment_received_amount = serializers.SerializerMethodField()
    payment_remaining_amount = serializers.SerializerMethodField()
    pending_payment = serializers.SerializerMethodField()
    follow_up_text = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = "__all__"
        read_only_fields = ["invoice_number"]

    def validate(self, data):
        """验证发票数据"""
        amount = data.get("amount")
        tax_rate = data.get("tax_rate")

        # 金额必须大于0
        if amount is not None and amount <= 0:
            raise serializers.ValidationError({"amount": "金额必须大于0"})

        # 税率必须在合理范围内
        if tax_rate is not None and (tax_rate < 0 or tax_rate > 100):
            raise serializers.ValidationError({"tax_rate": "税率必须在0-100之间"})

        return data

    def get_payment_received_amount(self, obj):
        received = getattr(obj, "received_payment_amount", None)
        if received is not None:
            return received
        return (
            obj.payments.aggregate(total=Sum("applied_amount"))["total"]
            or Decimal("0")
        )

    def get_payment_remaining_amount(self, obj):
        total_amount = obj.total_amount or Decimal("0")
        received = self.get_payment_received_amount(obj) or Decimal("0")
        remaining = total_amount - received
        return remaining if remaining > 0 else Decimal("0")

    def get_pending_payment(self, obj) -> bool:
        if obj.status not in {"issued", "sent", "received"}:
            return False
        return self.get_payment_remaining_amount(obj) > 0

    def get_follow_up_text(self, obj) -> str:
        status = obj.status or ""
        if status == "draft":
            return "待提交开票"
        if status in {"cancelled", "refunded"}:
            return "已关闭"
        if status in {"issued", "sent"}:
            if not getattr(obj, "attachment", None):
                return "待补发票附件"
            return "待确认客户收票"
        if status == "received":
            remaining = self.get_payment_remaining_amount(obj)
            if remaining > 0:
                return f"待跟进收款 {remaining:.2f}"
            return "已收齐待对账"
        return "待跟进"


class InvoiceCreateSerializer(serializers.ModelSerializer):
    """发票创建序列化器"""

    class Meta:
        model = Invoice
        fields = [
            "invoice_type",
            "sales_order",
            "work_order",
            "customer",
            "amount",
            "tax_rate",
            "issue_date",
            "customer_tax_number",
            "customer_address",
            "customer_phone",
            "customer_bank",
            "customer_account",
            "notes",
        ]

    def validate(self, data):
        """验证创建数据"""
        # 必须选择客户
        if not data.get("customer"):
            raise serializers.ValidationError({"customer": "必须选择客户"})

        # 如果选择了客户订单，自动填充客户开票信息
        sales_order = data.get("sales_order")
        if sales_order and sales_order.customer:
            customer = sales_order.customer
            # 如果未提供客户开票信息，尝试从客户信息获取
            if not data.get("customer_tax_number"):
                data["customer_tax_number"] = getattr(customer, "tax_number", "")
            if not data.get("customer_address"):
                data["customer_address"] = customer.address
            if not data.get("customer_phone"):
                data["customer_phone"] = customer.phone

        return data


class InvoiceUpdateSerializer(serializers.ModelSerializer):
    """发票更新序列化器"""

    class Meta:
        model = Invoice
        fields = [
            "invoice_code",
            "invoice_type",
            "amount",
            "tax_rate",
            "issue_date",
            "status",
            "customer_tax_number",
            "customer_address",
            "customer_phone",
            "customer_bank",
            "customer_account",
            "notes",
            "attachment",
        ]


# ==================== 收款管理序列化器 ====================


class PaymentSerializer(serializers.ModelSerializer):
    """收款记录序列化器"""

    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )

    # 关联信息
    sales_order_number = serializers.CharField(
        source="sales_order.order_number", read_only=True, allow_null=True
    )
    invoice_number = serializers.CharField(
        source="invoice.invoice_number", read_only=True, allow_null=True
    )
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    recorded_by_name = serializers.CharField(
        source="recorded_by.username", read_only=True, allow_null=True
    )
    follow_up_text = serializers.SerializerMethodField()
    needs_invoice_link = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ["payment_number", "remaining_amount"]

    def get_follow_up_text(self, obj) -> str:
        remaining = obj.remaining_amount or Decimal("0")
        if remaining > 0:
            return f"待核销 {remaining:.2f}"
        if self.get_needs_invoice_link(obj):
            return "待关联发票"
        return "已完成"

    def get_needs_invoice_link(self, obj) -> bool:
        return not obj.invoice_id and bool(obj.sales_order_id)


class PaymentCreateSerializer(serializers.ModelSerializer):
    """收款创建序列化器"""

    applied_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )

    class Meta:
        model = Payment
        fields = [
            "sales_order",
            "invoice",
            "customer",
            "amount",
            "applied_amount",
            "payment_method",
            "payment_date",
            "bank_account",
            "transaction_number",
            "notes",
        ]

    def validate(self, data):
        """验证创建数据"""
        # 必须选择客户
        if not data.get("customer"):
            raise serializers.ValidationError({"customer": "必须选择客户"})

        # 收款金额必须大于0
        amount = data.get("amount")
        if amount and amount <= 0:
            raise serializers.ValidationError({"amount": "收款金额必须大于0"})

        # 核销金额校验
        applied_amount = data.get("applied_amount")
        if applied_amount is not None:
            if applied_amount < 0:
                raise serializers.ValidationError(
                    {"applied_amount": "核销金额不能为负数"}
                )
            if amount and applied_amount > amount:
                raise serializers.ValidationError(
                    {"applied_amount": "核销金额不能大于收款金额"}
                )

        # 付款日期不能晚于今天
        payment_date = data.get("payment_date")
        if payment_date and payment_date > timezone.now().date():
            raise serializers.ValidationError({"payment_date": "付款日期不能晚于今天"})

        return data

    def create(self, validated_data):
        """
        创建收款时，若绑定了销售订单或发票且未显式传入 applied_amount，
        默认全额核销（applied_amount = amount）。
        若需要记录为未核销预收款，请显式传入 applied_amount=0。
        """
        amount = validated_data.get("amount", Decimal("0"))
        applied_amount = validated_data.get("applied_amount")
        sales_order = validated_data.get("sales_order")
        invoice = validated_data.get("invoice")

        if applied_amount is None and (sales_order or invoice):
            validated_data["applied_amount"] = amount

        return super().create(validated_data)


class PaymentUpdateSerializer(serializers.ModelSerializer):
    """收款更新序列化器"""

    class Meta:
        model = Payment
        fields = [
            "amount",
            "payment_method",
            "payment_date",
            "bank_account",
            "transaction_number",
            "applied_amount",
            "notes",
        ]


class PaymentPlanSerializer(serializers.ModelSerializer):
    """收款计划序列化器"""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    sales_order_number = serializers.CharField(
        source="sales_order.order_number", read_only=True
    )
    customer_name = serializers.CharField(
        source="sales_order.customer.name", read_only=True, allow_null=True
    )
    remaining_amount = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    overdue_days = serializers.SerializerMethodField()
    follow_up_text = serializers.SerializerMethodField()

    class Meta:
        model = PaymentPlan
        fields = "__all__"

    def get_progress_percentage(self, obj) -> int:
        """获取收款进度"""
        if obj.plan_amount > 0:
            return int((obj.paid_amount / obj.plan_amount) * 100)
        return 0

    def get_remaining_amount(self, obj):
        remaining = (obj.plan_amount or Decimal("0")) - (obj.paid_amount or Decimal("0"))
        return remaining if remaining > 0 else Decimal("0")

    def get_is_overdue(self, obj) -> bool:
        return obj.status != "completed" and obj.plan_date < timezone.localdate()

    def get_overdue_days(self, obj) -> int:
        if not self.get_is_overdue(obj):
            return 0
        return (timezone.localdate() - obj.plan_date).days

    def get_follow_up_text(self, obj) -> str:
        remaining = self.get_remaining_amount(obj)
        if obj.status == "completed":
            return "已完成"
        if self.get_is_overdue(obj):
            return f"已逾期 {self.get_overdue_days(obj)} 天，待收 {remaining:.2f}"
        if obj.status == "partial":
            return f"已部分收款，待收 {remaining:.2f}"
        if obj.plan_date == timezone.localdate():
            return f"今日待收 {remaining:.2f}"
        return f"按计划待收 {remaining:.2f}"


# ==================== 对账管理序列化器 ====================


class StatementSerializer(serializers.ModelSerializer):
    """对账单序列化器"""

    statement_type_display = serializers.CharField(
        source="get_statement_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    # 关联信息
    customer_name = serializers.CharField(
        source="customer.name", read_only=True, allow_null=True
    )
    supplier_name = serializers.CharField(
        source="supplier.name", read_only=True, allow_null=True
    )
    partner_name = serializers.SerializerMethodField()  # 统一的对方单位名称
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, allow_null=True
    )
    confirmed_by_name = serializers.CharField(
        source="confirmed_by.username", read_only=True, allow_null=True
    )

    statement_date = serializers.SerializerMethodField()
    follow_up_text = serializers.SerializerMethodField()

    class Meta:
        model = Statement
        fields = "__all__"
        read_only_fields = ["statement_number", "closing_balance"]

    def get_statement_date(self, obj):
        """返回创建日期（避免 DateField 直接处理 datetime）"""
        if not obj.created_at:
            return None
        return obj.created_at.date()

    def get_partner_name(self, obj) -> Optional[str]:
        """获取对方单位名称"""
        if obj.statement_type == "customer" and obj.customer:
            return obj.customer.name
        elif obj.statement_type == "supplier" and obj.supplier:
            return obj.supplier.name
        return None

    def get_follow_up_text(self, obj) -> str:
        status = obj.status or ""
        if status in {"draft", "sent"}:
            return "待对方确认"
        if status == "disputed":
            return "待财务处理异议"
        if status == "confirmed":
            return "已闭环"
        return "待跟进"


class StatementCreateSerializer(serializers.ModelSerializer):
    """对账单创建序列化器"""

    class Meta:
        model = Statement
        fields = [
            "statement_type",
            "customer",
            "supplier",
            "period",
            "start_date",
            "end_date",
            "opening_balance",
            "total_debit",
            "total_credit",
            "notes",
        ]

    def validate(self, data):
        """验证创建数据"""
        statement_type = data.get("statement_type")

        # 客户对账单必须选择客户
        if statement_type == "customer" and not data.get("customer"):
            raise serializers.ValidationError({"customer": "客户对账单必须选择客户"})

        # 供应商对账单必须选择供应商
        if statement_type == "supplier" and not data.get("supplier"):
            raise serializers.ValidationError(
                {"supplier": "供应商对账单必须选择供应商"}
            )

        # 结束日期必须晚于开始日期
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "结束日期必须晚于或等于开始日期"}
            )

        return data

    def create(self, validated_data):
        """创建对账单时自动设置创建人"""
        # 从 context 中获取 user
        request = self.context.get("request")
        if request and request.user:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


# ==================== 成本分析序列化器 ====================


class CostAnalysisSerializer(serializers.Serializer):
    """成本分析序列化器（用于统计报表）"""

    period = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    profit_rate = serializers.DecimalField(max_digits=5, decimal_places=2)

    # 成本明细
    material_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    labor_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    equipment_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    overhead_cost = serializers.DecimalField(max_digits=12, decimal_places=2)

    # 对比分析
    standard_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    actual_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    variance = serializers.DecimalField(max_digits=12, decimal_places=2)


# ==================== 导出所有序列化器 ====================

__all__ = [
    # 成本核算
    "CostCenterSerializer",
    "CostItemSerializer",
    "ProductionCostSerializer",
    "ProductionCostUpdateSerializer",
    # 发票管理
    "InvoiceSerializer",
    "InvoiceCreateSerializer",
    "InvoiceUpdateSerializer",
    # 收款管理
    "PaymentSerializer",
    "PaymentCreateSerializer",
    "PaymentUpdateSerializer",
    "PaymentPlanSerializer",
    # 对账管理
    "StatementSerializer",
    "StatementCreateSerializer",
    # 成本分析
    "CostAnalysisSerializer",
]
