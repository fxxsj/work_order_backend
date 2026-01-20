"""
库存管理 Admin

包含库存相关的 admin 类：
- ProductStockAdmin: 成品库存管理（已注释，暂不注册）
- StockInAdmin: 入库单管理（已注释，暂不注册）
- StockOutAdmin: 出库单管理（已注释，暂不注册）
- DeliveryOrderAdmin: 发货单管理
- DeliveryItemAdmin: 发货明细管理
- QualityInspectionAdmin: 质量检验管理（已注释，暂不注册）

及相关的 Inline 类：
- DeliveryItemInline: 发货明细内联
"""
from django.contrib import admin
from django.utils.html import format_html
from ..models import ProductStock, StockIn, StockOut, DeliveryOrder, DeliveryItem, QualityInspection
from .mixins import FixedInlineModelAdminMixin
from .utils import (
    create_status_badge_method,
    STOCK_STATUS_COLORS,
    IN_OUT_ORDER_STATUS_COLORS,
    QUALITY_STATUS_COLORS,
)


# ==================== Inline 类 ====================

class DeliveryItemInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """发货明细内联"""
    model = DeliveryItem
    extra = 1
    fields = ['product', 'quantity', 'unit', 'unit_price', 'subtotal']


# ==================== Admin 类 ====================

# @admin.register(StockIn)
class StockInAdmin(admin.ModelAdmin):
    """入库单管理（已注释，暂不注册）"""
    list_display = [
        'order_number', 'product_name', 'batch_number',
        'quantity', 'unit', 'status_badge',
        'stock_in_date', 'approved_by_name', 'created_at'
    ]
    search_fields = ['order_number', 'product__name', 'batch_number']
    list_filter = ['status', 'stock_in_date', 'approved_at', 'created_at']
    autocomplete_fields = ['product', 'work_order', 'approved_by', 'created_by']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('order_number', 'product', 'work_order', 'status')
        }),
        ('数量信息', {
            'fields': ('quantity', 'unit', 'batch_number')
        }),
        ('位置信息', {
            'fields': ('location', 'warehouse_area')
        }),
        ('日期信息', {
            'fields': ('production_date', 'expiry_date', 'stock_in_date')
        ('日期信息', {
            'fields': ('outbound_date',)
        }),
        ('其他信息', {
            'fields': ('notes',)
        }),
        ('系统信息', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def product_name(self, obj):
        """显示产品名称"""
        return obj.product.name
    product_name.short_description = '产品'

    # 出库单状态徽章
    status_badge = create_status_badge_method({
        'pending': '#909399',
        'completed': '#67C23A',
        'cancelled': '#F56C6C',
    })


@admin.register(DeliveryOrder)
class DeliveryOrderAdmin(admin.ModelAdmin):
    """发货单管理"""
    list_display = [
        'order_number', 'customer_name', 'sales_order_number',
        'receiver_name', 'logistics_company', 'tracking_number',
        'status_badge', 'delivery_date', 'created_at'
    ]
    search_fields = ['order_number', 'customer__name', 'sales_order__order_number', 'tracking_number']
    list_filter = ['status', 'delivery_date', 'created_at']
    autocomplete_fields = ['customer', 'sales_order', 'created_by']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [DeliveryItemInline]

    fieldsets = (
        ('基本信息', {
            'fields': ('order_number', 'customer', 'sales_order', 'status')
        }),
        ('收货信息', {
            'fields': ('receiver_name', 'receiver_phone', 'delivery_address')
        }),
        ('物流信息', {
            'fields': ('logistics_company', 'tracking_number', 'logistics_fee')
        }),
        ('发货信息', {
            'fields': ('delivery_date', 'freight', 'package_count')
        }),
        ('签收信息', {
            'fields': ('received', 'received_date', 'received_notes', 'receiver_signature')
        }),
        ('其他信息', {
            'fields': ('notes', 'attachment')
        }),
        ('系统信息', {
            'fields': ('created_by', 'created_at', 'updated_at'),

    def product_name(self, obj):
        """显示产品名称"""
        return obj.product.name
    product_name.short_description = '产品'


# @admin.register(QualityInspection)
class QualityInspectionAdmin(admin.ModelAdmin):
    """质量检验管理（已注释，暂不注册）"""
    list_display = [
        'inspection_number', 'product_name', 'batch_number',
        'inspection_type_display', 'result_badge', 'status_badge',
        'inspection_date', 'inspector_name', 'defective_rate', 'created_at'
    ]
    search_fields = ['inspection_number', 'product__name', 'batch_number']
    list_filter = ['inspection_type', 'result', 'status', 'inspection_date', 'created_at']
    autocomplete_fields = ['product', 'work_order', 'stock_in', 'inspector', 'created_by']
    readonly_fields = ['inspection_number', 'defective_rate', 'qualified_rate', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('inspection_number', 'product', 'work_order', 'stock_in')
        }),
        ('检验信息', {
            'fields': ('inspection_type', 'status', 'inspection_date', 'inspector', 'standard')
        }),
        ('数量信息', {
            'fields': ('inspection_quantity', 'sample_quantity', 'qualified_quantity', 'defective_quantity')
        }),
        ('质量指标', {
            'fields': ('defective_rate', 'qualified_rate')
        }),
        ('结果信息', {
            'fields': ('result', 'disposition', 'inspection_notes')
        }),
        ('处理信息', {
            'fields': ('rework_quantity', 'scrap_quantity', 'return_quantity', 'special_use_quantity'),
            'classes': ('collapse',)
        }),
        ('附件', {
            'fields': ('attachment',),
            'classes': ('collapse',)
        }),
        ('系统信息', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def product_name(self, obj):
        """显示产品名称"""
        return obj.product.name
    product_name.short_description = '产品'

    def inspector_name(self, obj):
        """显示检验员"""
        return obj.inspector.username if obj.inspector else '-'
    inspector_name.short_description = '检验员'

    def result_badge(self, obj):
        """结果徽章"""
        colors = {
            'passed': '#67C23A',
            'failed': '#F56C6C',
            'conditional': '#E6A23C',
        }
        return format_html(
            '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
            'background-color: {};">{}</span>',
            colors.get(obj.result, '#909399'),
            obj.get_result_display()
        )
    result_badge.short_description = '检验结果'

    # 质检状态徽章
    status_badge = create_status_badge_method({
        'pending': '#909399',
        'in_progress': '#E6A23C',
        'completed': '#67C23A',
    })
