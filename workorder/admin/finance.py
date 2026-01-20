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
from django.utils.html import format_html
from ..models import CostCenter, CostItem, ProductionCost, Invoice, Payment, PaymentPlan, Statement
from .utils import create_status_badge_method, FINANCE_STATUS_COLORS


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    """成本中心管理"""
    list_display = ['code', 'name', 'type', 'parent', 'is_active', 'created_at']
    search_fields = ['code', 'name', 'description']
    list_filter = ['type', 'is_active', 'created_at']
    list_editable = ['is_active']
    ordering = ['code']
        ('其他信息', {
            'fields': ('notes', 'attachment')
        }),
        ('系统信息', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def customer_name(self, obj):
        """显示客户名称"""
        return obj.customer.name
    customer_name.short_description = '客户'

    def created_by_name(self, obj):
        """显示创建人"""
        return obj.created_by.username if obj.created_by else '-'
    created_by_name.short_description = '创建人'


# @admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    """收款计划管理（已注释，暂不注册）"""
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
        ('基本信息', {
            'fields': ('sales_order', 'customer', 'plan_name', 'status')
        }),
        ('金额信息', {
            'fields': ('amount', 'payment_ratio', 'paid_amount', 'remaining_amount')
        }),
        ('日期信息', {
            'fields': ('planned_date', 'actual_payment_date')
        }),
        ('关联收款', {
            'fields': ('payment',)
        }),
        ('其他信息', {
            'fields': ('notes',)
        }),
        ('系统信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def sales_order_number(self, obj):
        """显示销售订单号"""
        return obj.sales_order.order_number if obj.sales_order else '-'
    sales_order_number.short_description = '销售订单'

    def customer_name(self, obj):
        """显示客户名称"""
        return obj.customer.name
    customer_name.short_description = '客户'


# @admin.register(Statement)
class StatementAdmin(admin.ModelAdmin):
    """对账单管理（已注释，暂不注册）"""
    list_display = [
        'statement_number', 'statement_type_display', 'partner_name',
        'period_start', 'period_end', 'opening_balance',
        'debit_amount', 'credit_amount', 'closing_balance',
        'status_badge', 'confirmed_at', 'created_at'
    ]
    search_fields = ['statement_number', 'partner__name']
    list_filter = ['statement_type', 'status', 'period_start', 'period_end', 'confirmed_at', 'created_at']
    autocomplete_fields = ['partner', 'confirmed_by', 'created_by']
    readonly_fields = ['statement_number', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('statement_number', 'statement_type', 'partner', 'status')
        }),
        ('对账期间', {
            'fields': ('period_start', 'period_end', 'statement_date')
        }),
        ('余额信息', {
            'fields': ('opening_balance', 'debit_amount', 'credit_amount', 'closing_balance')
        }),
        ('确认信息', {
            'fields': ('confirmed_by', 'confirmed_at', 'confirm_notes')
        }),
        ('其他信息', {
            'fields': ('notes', 'attachment')
        }),
        ('系统信息', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

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
