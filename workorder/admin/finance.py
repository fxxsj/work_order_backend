"""
财务管理 Admin

包含财务相关的 admin 类：
- CostCenterAdmin: 成本中心管理
- CostItemAdmin: 成本项目管理
- ProductionCostAdmin: 生产成本管理
- InvoiceAdmin: 发票管理
- PaymentAdmin: 收款记录管理（已注释，暂不注册）
- PaymentPlanAdmin: 收款计划管理（已注释，暂不注册）
- StatementAdmin: 对账单管理（已注释，暂不注册）
"""

from django.contrib import admin

from ..models import (
    CostCenter,
    CostItem,
    Invoice,
    Payment,
    PaymentPlan,
    ProductionCost,
    Statement,
    SupplierPayment,
)
from .utils import create_status_badge_method


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    """成本中心管理"""

    list_display = [
        "code",
        "name",
        "type",
        "parent",
        "is_active",
        "created_at",
    ]
    search_fields = ["code", "name", "description"]
    list_filter = ["type", "is_active", "created_at"]
    list_editable = ["is_active"]
    ordering = ["code"]
    autocomplete_fields = ["parent", "manager"]
    readonly_fields = ["created_at", "updated_at"]
    list_select_related = ["parent", "manager"]

    fieldsets = (
        (
            "基本信息",
            {"fields": ("code", "name", "type", "parent", "is_active")},
        ),
        ("详细信息", {"fields": ("description", "manager")}),
        (
            "系统信息",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(CostItem)
class CostItemAdmin(admin.ModelAdmin):
    """成本项目管理"""

    list_display = [
        "code",
        "name",
        "type",
        "allocation_method",
        "is_active",
        "created_at",
    ]
    search_fields = ["code", "name", "description"]
    list_filter = ["type", "allocation_method", "is_active", "created_at"]
    list_editable = ["is_active"]
    ordering = ["code"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "基本信息",
            {
                "fields": (
                    "code",
                    "name",
                    "type",
                    "allocation_method",
                    "is_active",
                )
            },
        ),
        ("详细信息", {"fields": ("description",)}),
        (
            "系统信息",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(ProductionCost)
class ProductionCostAdmin(admin.ModelAdmin):
    """生产成本管理"""

    list_display = [
        "work_order",
        "period",
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
    ]
    search_fields = ["work_order__order_number", "period"]
    list_filter = ["calculated_at", "created_at"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["work_order", "calculated_by"]
    ordering = ["-created_at"]
    list_select_related = ["work_order", "calculated_by"]

    fieldsets = (
        ("基本信息", {"fields": ("work_order", "period")}),
        (
            "实际成本",
            {
                "fields": (
                    "material_cost",
                    "labor_cost",
                    "equipment_cost",
                    "overhead_cost",
                    "total_cost",
                )
            },
        ),
        ("标准成本", {"fields": ("standard_cost",)}),
        ("差异分析", {"fields": ("variance", "variance_rate")}),
        ("其他信息", {"fields": ("calculated_at", "calculated_by", "notes")}),
        (
            "系统信息",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """发票管理"""

    list_display = [
        "invoice_number",
        "customer",
        "invoice_type",
        "status",
        "issue_date",
        "amount",
        "tax_amount",
        "total_amount",
        "submitted_by",
        "approved_by",
        "created_at",
    ]
    search_fields = ["invoice_number", "customer__name", "notes"]
    list_filter = [
        "invoice_type",
        "status",
        "issue_date",
        "submitted_at",
        "approved_at",
        "created_at",
    ]
    autocomplete_fields = [
        "customer",
        "submitted_by",
        "approved_by",
        "created_by",
        "sales_order",
        "work_order",
    ]
    list_select_related = [
        "customer",
        "submitted_by",
        "approved_by",
        "created_by",
    ]
    readonly_fields = [
        "invoice_number",
        "tax_amount",
        "total_amount",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "基本信息",
            {
                "fields": (
                    "invoice_number",
                    "customer",
                    "invoice_type",
                    "status",
                )
            },
        ),
        (
            "金额信息",
            {"fields": ("amount", "tax_rate", "tax_amount", "total_amount")},
        ),
        ("关联信息", {"fields": ("sales_order", "work_order", "notes")}),
        ("日期信息", {"fields": ("issue_date",)}),
        (
            "审核信息",
            {
                "fields": (
                    "submitted_by",
                    "submitted_at",
                    "approved_by",
                    "approved_at",
                )
            },
        ),
        (
            "其他信息",
            {
                "fields": (
                    "customer_tax_number",
                    "customer_address",
                    "customer_phone",
                    "customer_bank",
                    "customer_account",
                    "attachment",
                )
            },
        ),
        (
            "系统信息",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """收款记录管理"""

    list_display = [
        "payment_number",
        "customer",
        "sales_order",
        "invoice",
        "payment_date",
        "get_payment_method_display",
        "amount",
        "applied_amount",
        "remaining_amount",
        "recorded_by",
        "created_at",
    ]
    search_fields = [
        "payment_number",
        "customer__name",
        "transaction_number",
        "bank_account",
    ]
    list_filter = ["payment_method", "payment_date", "created_at"]
    autocomplete_fields = ["customer", "sales_order", "invoice", "recorded_by"]
    readonly_fields = ["payment_number", "remaining_amount", "created_at"]
    ordering = ["-payment_date", "-created_at"]
    list_select_related = ["customer", "sales_order", "invoice", "recorded_by"]

    fieldsets = (
        (
            "基本信息",
            {
                "fields": (
                    "payment_number",
                    "customer",
                    "sales_order",
                    "invoice",
                    "payment_date",
                    "payment_method",
                )
            },
        ),
        (
            "金额信息",
            {"fields": ("amount", "applied_amount", "remaining_amount")},
        ),
        ("支付信息", {"fields": ("bank_account", "transaction_number")}),
        ("其他信息", {"fields": ("notes",)}),
        (
            "系统信息",
            {
                "fields": ("recorded_by", "created_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    """收款计划管理"""

    list_display = [
        "sales_order_number",
        "customer_name",
        "plan_amount",
        "plan_date",
        "status",
        "paid_amount",
        "remaining_amount",
        "created_at",
    ]
    search_fields = [
        "sales_order__order_number",
        "sales_order__customer__name",
        "notes",
    ]
    list_filter = ["status", "plan_date", "created_at"]
    autocomplete_fields = ["sales_order"]
    readonly_fields = ["created_at", "remaining_amount"]
    ordering = ["plan_date", "sales_order"]
    list_select_related = ["sales_order"]

    fieldsets = (
        ("基本信息", {"fields": ("sales_order", "status")}),
        (
            "金额信息",
            {"fields": ("plan_amount", "paid_amount", "remaining_amount")},
        ),
        ("日期信息", {"fields": ("plan_date",)}),
        ("其他信息", {"fields": ("notes",)}),
        (
            "系统信息",
            {"fields": ("created_at",), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="客户订单")
    def sales_order_number(self, obj):
        """显示客户订单号"""
        return obj.sales_order.order_number if obj.sales_order else "-"

    @admin.display(description="客户")
    def customer_name(self, obj):
        """显示客户名称"""
        return obj.sales_order.customer.name if obj.sales_order_id else "-"

    @admin.display(description="剩余金额")
    def remaining_amount(self, obj):
        return obj.plan_amount - obj.paid_amount


@admin.register(Statement)
class StatementAdmin(admin.ModelAdmin):
    """对账单管理"""

    list_display = [
        "statement_number",
        "get_statement_type_display",
        "partner_name",
        "period",
        "start_date",
        "end_date",
        "opening_balance",
        "total_debit",
        "total_credit",
        "closing_balance",
        "status_badge",
        "confirmed_at",
        "created_at",
    ]
    search_fields = [
        "statement_number",
        "customer__name",
        "supplier__name",
        "period",
    ]
    list_filter = [
        "statement_type",
        "status",
        "start_date",
        "end_date",
        "confirmed_at",
        "created_at",
    ]
    autocomplete_fields = [
        "customer",
        "supplier",
        "confirmed_by",
        "created_by",
    ]
    readonly_fields = ["statement_number", "closing_balance", "created_at"]
    ordering = ["-created_at"]
    list_select_related = [
        "customer",
        "supplier",
        "confirmed_by",
        "created_by",
    ]

    fieldsets = (
        (
            "基本信息",
            {
                "fields": (
                    "statement_number",
                    "statement_type",
                    "customer",
                    "supplier",
                    "status",
                )
            },
        ),
        ("对账期间", {"fields": ("period", "start_date", "end_date")}),
        (
            "余额信息",
            {
                "fields": (
                    "opening_balance",
                    "total_debit",
                    "total_credit",
                    "closing_balance",
                )
            },
        ),
        (
            "确认信息",
            {"fields": ("confirmed_by", "confirmed_at", "confirmation_notes")},
        ),
        ("其他信息", {"fields": ("notes",)}),
        (
            "系统信息",
            {
                "fields": ("created_by", "created_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="对方单位")
    def partner_name(self, obj):
        if obj.customer_id:
            return obj.customer.name
        if obj.supplier_id:
            return obj.supplier.name
        return "-"

    # 发票状态徽章
    status_badge = create_status_badge_method(
        {
            "draft": "#909399",
            "confirmed": "#67C23A",
            "cancelled": "#F56C6C",
        }
    )


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    """供应商付款管理"""

    list_display = [
        "payment_number",
        "supplier",
        "purchase_order",
        "amount",
        "applied_amount",
        "remaining_amount",
        "payment_method",
        "payment_date",
        "status",
        "created_at",
    ]
    search_fields = [
        "payment_number",
        "supplier__name",
        "purchase_order__order_number",
    ]
    list_filter = ["status", "payment_method", "payment_date", "created_at"]
    autocomplete_fields = [
        "supplier",
        "purchase_order",
        "created_by",
        "submitted_by",
        "approved_by",
    ]
    readonly_fields = ["payment_number", "remaining_amount", "created_at"]
    ordering = ["-payment_date"]
    list_select_related = ["supplier", "purchase_order"]
