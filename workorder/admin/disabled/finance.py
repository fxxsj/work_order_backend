"""
未启用的财务 Admin 类

这些 Admin 类暂时未注册到 Django Admin，待功能完善后再启用。

包含的类：
- PaymentAdmin: 收款记录管理（待启用）
- PaymentPlanAdmin: 收款计划管理（待启用）
- StatementAdmin: 对账单管理（待启用）
"""

from django.contrib import admin
from django.utils.html import format_html
from ...models import Payment, PaymentPlan, Statement
from ..utils import create_status_badge_method, FINANCE_STATUS_COLORS


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """收款记录管理"""
    list_display = [
        'payment_number', 'customer_name', 'payment_date',
        'payment_method_display', 'amount', 'applied_amount',
        'remaining_amount', 'created_by_name', 'created_at'
    ]
    search_fields = ['payment_number', 'customer__name', 'transaction_number', 'bank_account']
    list_filter = ['payment_method', 'payment_date', 'created_at']
    autocomplete_fields = ['customer', 'created_by']
    readonly_fields = ['payment_number', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('基本信息', {'fields': ('payment_number', 'customer', 'payment_date', 'payment_method')}),
        ('金额信息', {'fields': ('amount', 'applied_amount', 'remaining_amount')}),
        ('支付信息', {'fields': ('bank_account', 'transaction_number')}),
        ('其他信息', {'fields': ('notes', 'attachment')}),
        ('系统信息', {'fields': ('created_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def customer_name(self, obj):
        return obj.customer.name
    customer_name.short_description = '客户'

    def created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else '-'
    created_by_name.short_description = '创建人'


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    """收款计划管理"""
    list_display = [
        'sales_order_number', 'customer_name', 'plan_name',
        'amount', 'planned_date', 'status_display',
        'paid_amount', 'remaining_amount', 'created_at'
    ]
    search_fields = ['sales_order__order_number', 'customer__name', 'plan_name']
    list_filter = ['status', 'planned_date', 'actual_payment_date', 'created_at']
    autocomplete_fields = ['sales_order', 'customer', 'payment']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['planned_date']

    fieldsets = (
        ('基本信息', {'fields': ('sales_order', 'customer', 'plan_name', 'status')}),
        ('金额信息', {'fields': ('amount', 'payment_ratio', 'paid_amount', 'remaining_amount')}),
        ('日期信息', {'fields': ('planned_date', 'actual_payment_date')}),
        ('关联收款', {'fields': ('payment',)}),
        ('其他信息', {'fields': ('notes',)}),
        ('系统信息', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def sales_order_number(self, obj):
        return obj.sales_order.order_number if obj.sales_order else '-'
    sales_order_number.short_description = '销售订单'

    def customer_name(self, obj):
        return obj.customer.name
    customer_name.short_description = '客户'

    def status_display(self, obj):
        """状态显示"""
        colors = {
            'pending': '#909399',
            'partial': '#E6A23C',
            'paid': '#67C23A',
        }
        return format_html(
            '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
            'background-color: {};">{}</span>',
            colors.get(obj.status, '#909399'),
            obj.get_status_display()
        )
    status_display.short_description = '状态'


@admin.register(Statement)
class StatementAdmin(admin.ModelAdmin):
    """对账单管理"""
    list_display = [
        'statement_number', 'statement_type_display', 'partner_name',
        'period_start', 'period_end', 'opening_balance',
        'debit_amount', 'credit_amount', 'closing_balance',
        'status_badge', 'confirmed_at', 'created_at'
    ]
    search_fields = ['statement_number', 'partner__name']
    list_filter = ['statement_type', 'status', 'period_start', 'period_end', 'created_at']
    autocomplete_fields = ['partner', 'confirmed_by', 'created_by']
    readonly_fields = ['statement_number', 'created_at', 'updated_at']
    ordering = ['-period_start']

    fieldsets = (
        ('基本信息', {'fields': ('statement_number', 'statement_type', 'partner', 'status')}),
        ('账期信息', {'fields': ('period_start', 'period_end')}),
        ('余额信息', {'fields': ('opening_balance', 'debit_amount', 'credit_amount', 'closing_balance')}),
        ('确认信息', {'fields': ('confirmed_by', 'confirmed_at', 'confirmation_notes')}),
        ('其他信息', {'fields': ('notes', 'attachment')}),
        ('系统信息', {'fields': ('created_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def statement_type_display(self, obj):
        """单据类型显示"""
        return obj.get_statement_type_display()
    statement_type_display.short_description = '单据类型'

    def partner_name(self, obj):
        """显示对方单位名称"""
        return obj.partner.name if hasattr(obj.partner, 'name') else str(obj.partner)
    partner_name.short_description = '对方单位'

    # 发票状态徽章
    status_badge = create_status_badge_method({
        'draft': '#909399',
        'confirmed': '#67C23A',
        'cancelled': '#F56C6C',
    })
