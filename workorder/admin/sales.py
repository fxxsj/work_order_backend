"""
销售管理 Admin

包含销售相关的 admin 类：
- SalesOrderAdmin: 销售订单管理
- SalesOrderItemAdmin: 销售订单明细管理

及相关的 Inline 类：
- SalesOrderItemInline: 销售订单明细内联
"""
from django.contrib import admin
from django.utils.html import format_html
from ..models import SalesOrder, SalesOrderItem
from .mixins import FixedInlineModelAdminMixin
from .utils import create_status_badge_method, WORKORDER_STATUS_COLORS


# ==================== Inline 类 ====================

class SalesOrderItemInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """销售订单明细内联"""
    model = SalesOrderItem
    extra = 1
    fields = ['product', 'quantity', 'unit', 'unit_price', 'tax_rate', 'discount_amount', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'subtotal']


# ==================== Admin 类 ====================

@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    """销售订单管理"""
    list_display = [
        'order_number', 'customer_name', 'status_badge', 'payment_status_badge',
        'total_amount', 'submitted_by_name', 'approved_by_name', 'items_count',
        'order_date', 'delivery_date', 'created_at'
    ]
    list_filter = ['status', 'payment_status', 'customer', 'submitted_at', 'approved_at', 'created_at']
    search_fields = ['order_number', 'customer__name', 'work_orders__order_number']
    autocomplete_fields = ['customer', 'submitted_by', 'approved_by', 'created_by', 'work_orders']
    readonly_fields = ['order_number', 'subtotal', 'tax_amount', 'total_amount', 'created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [SalesOrderItemInline]

    fieldsets = (
        ('基本信息', {
            'fields': ('order_number', 'customer', 'status', 'payment_status')
        }),
        ('金额信息', {
            'fields': ('subtotal', 'tax_rate', 'tax_amount', 'discount_amount', 'total_amount')
        }),
        ('日期信息', {
            'fields': ('order_date', 'delivery_date', 'actual_delivery_date')
        }),
        ('付款信息', {
            'fields': ('deposit_amount', 'paid_amount', 'payment_date')
        }),
        ('审核信息', {
            'fields': ('submitted_by', 'submitted_at', 'approved_by', 'approved_at', 'approval_comment')
        }),
        ('联系与收货', {
            'fields': ('contact_person', 'contact_phone', 'shipping_address')
        }),
        ('其他信息', {
            'fields': ('work_orders', 'notes', 'rejection_reason')
        }),
        ('系统信息', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def customer_name(self, obj):
        """显示客户名称"""
        return obj.customer.name
    customer_name.short_description = '客户'

    # 销售订单状态徽章
    status_badge = create_status_badge_method({
        'draft': '#909399',
        'submitted': '#E6A23C',
        'approved': '#409EFF',
        'in_production': '#67C23A',
        'completed': '#67C23A',
        'cancelled': '#F56C6C',
    })

    # 付款状态徽章
    payment_status_badge = create_status_badge_method({
        'unpaid': '#F56C6C',
        'partial': '#E6A23C',
        'paid': '#67C23A',
    })

    def submitted_by_name(self, obj):
        """显示提交人"""
        return obj.submitted_by.username if obj.submitted_by else '-'
    submitted_by_name.short_description = '提交人'

    def approved_by_name(self, obj):
        """显示审核人"""
        return obj.approved_by.username if obj.approved_by else '-'
    approved_by_name.short_description = '审核人'

    def items_count(self, obj):
        """显示明细数量"""
        return obj.items.count()
    items_count.short_description = '明细数量'


@admin.register(SalesOrderItem)
class SalesOrderItemAdmin(admin.ModelAdmin):
    """销售订单明细管理"""
    list_display = [
        'sales_order_number', 'product_code', 'product_name',
        'quantity', 'unit', 'unit_price', 'tax_rate', 'discount_amount',
        'subtotal', 'created_at'
    ]
    list_filter = ['product', 'sales_order', 'created_at']
    search_fields = [
        'sales_order__order_number', 'product__name', 'product__code'
    ]
    autocomplete_fields = ['product', 'sales_order']
    readonly_fields = ['created_at', 'updated_at', 'subtotal']
    ordering = ['sales_order', 'id']

    def sales_order_number(self, obj):
        """显示销售订单号"""
        return obj.sales_order.order_number
    sales_order_number.short_description = '销售订单号'

    def product_code(self, obj):
        """显示产品编码"""
        return obj.product.code
    product_code.short_description = '产品编码'

    def product_name(self, obj):
        """显示产品名称"""
        return obj.product.name
    product_name.short_description = '产品名称'
