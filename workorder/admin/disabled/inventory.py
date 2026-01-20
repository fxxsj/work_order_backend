"""
未启用的库存 Admin 类

这些 Admin 类暂时未注册到 Django Admin，待功能完善后再启用。

包含的类：
- ProductStockAdmin: 成品库存管理（待启用）
- StockInAdmin: 入库单管理（待启用）
- StockOutAdmin: 出库单管理（待启用）
- QualityInspectionAdmin: 质量检验管理（待启用）
"""

from django.contrib import admin
from django.utils.html import format_html
from ...models import ProductStock, StockIn, StockOut, QualityInspection
from ..utils import create_status_badge_method, STOCK_STATUS_COLORS


@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    """成品库存管理"""
    list_display = [
        'product_code', 'product_name', 'batch_number',
        'quantity', 'reserved_quantity', 'available_quantity',
        'location', 'status_badge', 'production_date',
        'expiry_date', 'days_until_expiry', 'created_at'
    ]
    search_fields = ['product__name', 'product__code', 'batch_number', 'location']
    list_filter = ['status', 'production_date', 'expiry_date', 'created_at']
    autocomplete_fields = ['product']
    readonly_fields = ['created_at', 'updated_at', 'days_until_expiry', 'total_value']
    ordering = ['-created_at']

    fieldsets = (
        ('基本信息', {'fields': ('product', 'batch_number', 'status')}),
        ('数量信息', {'fields': ('quantity', 'reserved_quantity', 'available_quantity', 'min_stock_level')}),
        ('位置信息', {'fields': ('location', 'warehouse_area')}),
        ('日期信息', {'fields': ('production_date', 'expiry_date')}),
        ('成本信息', {'fields': ('unit_cost', 'total_value')}),
        ('其他信息', {'fields': ('notes',)}),
        ('系统信息', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def product_code(self, obj):
        return obj.product.code
    product_code.short_description = '产品编码'

    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = '产品'

    def available_quantity(self, obj):
        return obj.quantity - obj.reserved_quantity
    available_quantity.short_description = '可用数量'

    status_badge = create_status_badge_method(STOCK_STATUS_COLORS)


@admin.register(StockIn)
class StockInAdmin(admin.ModelAdmin):
    """入库单管理"""
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
        ('基本信息', {'fields': ('order_number', 'product', 'work_order', 'status')}),
        ('数量信息', {'fields': ('quantity', 'unit', 'batch_number')}),
        ('位置信息', {'fields': ('location', 'warehouse_area')}),
        ('日期信息', {'fields': ('production_date', 'expiry_date', 'stock_in_date')}),
        ('质量信息', {'fields': ('quality_inspection', 'inspection_result')}),
        ('审核信息', {'fields': ('approved_by', 'approved_at', 'approval_notes')}),
        ('其他信息', {'fields': ('notes', 'attachment')}),
        ('系统信息', {'fields': ('created_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = '产品'

    status_badge = create_status_badge_method({
        'draft': '#909399', 'submitted': '#E6A23C',
        'approved': '#67C23A', 'rejected': '#F56C6C',
    })

    def approved_by_name(self, obj):
        return obj.approved_by.username if obj.approved_by else '-'
    approved_by_name.short_description = '审核人'


@admin.register(StockOut)
class StockOutAdmin(admin.ModelAdmin):
    """出库单管理"""
    list_display = [
        'order_number', 'product_name', 'outbound_type_display',
        'quantity', 'unit', 'status_badge',
        'outbound_date', 'created_at'
    ]
    search_fields = ['order_number', 'product__name']
    list_filter = ['outbound_type', 'status', 'outbound_date', 'created_at']
    autocomplete_fields = ['product', 'delivery_order', 'created_by']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('基本信息', {'fields': ('order_number', 'product', 'outbound_type', 'status')}),
        ('数量信息', {'fields': ('quantity', 'unit', 'batch_number')}),
        ('关联信息', {'fields': ('delivery_order', 'related_order')}),
        ('日期信息', {'fields': ('outbound_date',)}),
        ('其他信息', {'fields': ('notes',)}),
        ('系统信息', {'fields': ('created_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = '产品'

    status_badge = create_status_badge_method({
        'pending': '#909399', 'completed': '#67C23A', 'cancelled': '#F56C6C',
    })


@admin.register(QualityInspection)
class QualityInspectionAdmin(admin.ModelAdmin):
    """质量检验管理"""
    list_display = [
        'inspection_number', 'product_name', 'batch_number',
        'inspection_type_display', 'result_badge', 'status_badge',
        'inspection_date', 'inspector_name', 'defective_rate', 'created_at'
    ]
    search_fields = ['inspection_number', 'product__name', 'batch_number']
    list_filter = ['inspection_type', 'result', 'status', 'inspection_date', 'created_at']
    autocomplete_fields = ['product', 'work_order', 'stock_in', 'inspector', 'created_by']
    readonly_fields = ['inspection_number', 'created_at', 'updated_at', 'defective_rate']
    ordering = ['-created_at']

    fieldsets = (
        ('基本信息', {'fields': ('inspection_number', 'product', 'inspection_type', 'status')}),
        ('批次信息', {'fields': ('batch_number', 'quantity')}),
        ('检验信息', {'fields': ('inspection_date', 'inspector', 'result')}),
        ('缺陷统计', {'fields': ('defective_quantity', 'defective_rate', 'defect_types')}),
        ('关联信息', {'fields': ('work_order', 'stock_in')}),
        ('其他信息', {'fields': ('notes', 'attachment')}),
        ('系统信息', {'fields': ('created_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = '产品'

    def inspection_type_display(self, obj):
        return obj.get_inspection_type_display()
    inspection_type_display.short_description = '检验类型'

    def result_badge(self, obj):
        colors = {'pending': '#909399', 'passed': '#67C23A', 'failed': '#F56C6C'}
        return format_html(
            '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
            'background-color: {};">{}</span>',
            colors.get(obj.result, '#909399'),
            obj.get_result_display()
        )
    result_badge.short_description = '检验结果'

    status_badge = create_status_badge_method({
        'pending': '#909399', 'in_progress': '#E6A23C', 'completed': '#67C23A',
    })

    def inspector_name(self, obj):
        return obj.inspector.username if obj.inspector else '-'
    inspector_name.short_description = '检验人'
