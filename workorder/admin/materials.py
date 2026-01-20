"""
物料采购管理 Admin

包含物料采购相关的 admin 类：
- MaterialAdmin: 物料管理
- SupplierAdmin: 供应商管理
- MaterialSupplierAdmin: 物料供应商关联管理
- PurchaseOrderAdmin: 采购单管理
- PurchaseOrderItemAdmin: 采购单明细管理

及相关的 Inline 类：
- PurchaseOrderItemInline: 采购单明细内联
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum
from ..models import Material, Supplier, MaterialSupplier, PurchaseOrder, PurchaseOrderItem
from .mixins import FixedInlineModelAdminMixin
from .utils import create_status_badge_method, PURCHASE_STATUS_COLORS


# ==================== Inline 类 ====================

class PurchaseOrderItemInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """采购单明细内联"""
    model = PurchaseOrderItem
    extra = 1
    fields = ['material', 'quantity', 'received_quantity', 'unit_price', 'status', 'notes']
    readonly_fields = ['created_at', 'updated_at']


# ==================== Admin 类 ====================

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    """物料管理"""
    list_display = ['code', 'name', 'specification', 'unit', 'unit_price',
                    'stock_quantity', 'created_at']
    search_fields = ['code', 'name', 'specification']
    list_filter = ['unit', 'created_at']
    list_editable = ['unit_price', 'stock_quantity']


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    """供应商管理（优化版）"""
    list_display = ['code', 'name', 'contact_person', 'phone', 'email', 'status', 'material_count', 'created_at']
    search_fields = ['code', 'name', 'contact_person', 'phone', 'email']
    list_filter = ['status', 'created_at']
    list_editable = ['status']
    ordering = ['code']
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        """优化查询性能"""
        qs = super().get_queryset(request)
        # 使用注解预计算物料数量
        qs = qs.annotate(
            _material_count=Count('materialsupplier')
        )
        return qs

    def material_count(self, obj):
        """显示供应物料数量（优化版）"""
        return getattr(obj, '_material_count', obj.default_materials.count())
    material_count.short_description = '供应物料数'
    material_count.admin_order_field = '_material_count'


@admin.register(MaterialSupplier)
class MaterialSupplierAdmin(admin.ModelAdmin):
    """物料供应商关联管理"""
    list_display = ['material_code', 'material_name', 'supplier_code', 'supplier_name', 'supplier_price', 'is_preferred', 'lead_time_days', 'min_order_quantity']
    list_filter = ['is_preferred', 'created_at']
    search_fields = ['material__name', 'material__code', 'supplier__name', 'supplier__code']
    list_editable = ['is_preferred', 'supplier_price', 'min_order_quantity', 'lead_time_days']
    ordering = ['material', 'supplier']
    readonly_fields = ['created_at']

    def material_code(self, obj):
        """显示物料编码"""
        return obj.material.code
    material_code.short_description = '物料编码'

    def material_name(self, obj):
        """显示物料名称"""
        return obj.material.name
    material_name.short_description = '物料名称'

    def supplier_code(self, obj):
        """显示供应商编码"""
        return obj.supplier.code
    supplier_code.short_description = '供应商编码'

    def supplier_name(self, obj):
        """显示供应商名称"""
        return obj.supplier.name
    supplier_name.short_description = '供应商名称'


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    """采购单管理（优化版）"""
    list_display = [
        'order_number', 'supplier_name', 'status_badge', 'total_amount',
        'submitted_by_name', 'approved_by_name', 'items_count',
        'received_progress', 'created_at'
    ]
    list_filter = ['status', 'supplier', 'submitted_at', 'approved_at', 'created_at']
    search_fields = ['order_number', 'supplier__name', 'work_order__order_number']
    autocomplete_fields = ['supplier', 'work_order']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [PurchaseOrderItemInline]

    fieldsets = (
        ('基本信息', {
            'fields': ('order_number', 'supplier', 'work_order', 'status')
        }),
        ('审核信息', {
            'fields': ('submitted_by', 'submitted_at', 'approved_by', 'approved_at')
        }),
        ('采购时间', {
            'fields': ('ordered_date', 'expected_date', 'actual_received_date')
        }),
        ('其他信息', {
            'fields': ('total_amount', 'notes', 'rejection_reason')
        }),
        ('系统信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """优化查询性能"""
        qs = super().get_queryset(request)
        qs = qs.select_related(
            'supplier', 'submitted_by', 'approved_by'
        ).prefetch_related(
            'items__material'
        )

        # 使用注解优化items_count和received_progress
        qs = qs.annotate(
            _items_count=Count('items'),
            _total_quantity=Sum('items__quantity'),
            _total_received=Sum('items__received_quantity')
        )

        return qs

    def supplier_name(self, obj):
        """显示供应商名称"""
        return obj.supplier.name
    supplier_name.short_description = '供应商'

    def submitted_by_name(self, obj):
        """显示提交人"""
        return obj.submitted_by.username if obj.submitted_by else '-'
    submitted_by_name.short_description = '提交人'

    def approved_by_name(self, obj):
        """显示审核人"""
        return obj.approved_by.username if obj.approved_by else '-'
    approved_by_name.short_description = '审核人'

    def items_count(self, obj):
        """显示明细数量（优化版）"""
        return getattr(obj, '_items_count', obj.items.count())
    items_count.short_description = '明细数量'

    def received_progress(self, obj):
        """显示收货进度（优化版）"""
        # 使用预计算的注解字段
        if hasattr(obj, '_total_quantity') and hasattr(obj, '_total_received'):
            total_quantity = obj._total_quantity or 0
            total_received = obj._total_received or 0
        else:
            # 回退方案
            items = obj.items.all()
            if not items:
                return '-'
            total_quantity = sum(item.quantity for item in items)
            total_received = sum(item.received_quantity for item in items)

        if total_quantity == 0:
            return '0%'

        percentage = round((total_received / total_quantity) * 100, 2)
        color = '#67C23A' if percentage >= 100 else '#409EFF' if percentage >= 50 else '#E6A23C'

        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; height: 20px; background-color: {}; border-radius: 3px; '
            'text-align: center; color: white; line-height: 20px;">{}%</div></div>',
            percentage, color, percentage
        )
    received_progress.short_description = '收货进度'

    # 采购单状态徽章
    status_badge = create_status_badge_method({
        'draft': '#909399',
        'submitted': '#E6A23C',
        'approved': '#409EFF',
        'ordered': '#67C23A',
        'received': '#67C23A',
        'cancelled': '#F56C6C',
    })


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    """采购单明细管理"""
    list_display = [
        'purchase_order_number', 'material_code', 'material_name',
        'quantity', 'received_quantity', 'unit_price', 'subtotal',
        'status_badge', 'created_at'
    ]
    list_filter = ['status', 'material', 'purchase_order', 'created_at']
    search_fields = [
        'purchase_order__order_number', 'material__name', 'material__code'
    ]
    autocomplete_fields = ['material', 'purchase_order', 'work_order_material']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['purchase_order', 'id']

    def purchase_order_number(self, obj):
        """显示采购单号"""
        return obj.purchase_order.order_number
    purchase_order_number.short_description = '采购单号'

    def material_code(self, obj):
        """显示物料编码"""
        return obj.material.code
    material_code.short_description = '物料编码'

    def material_name(self, obj):
        """显示物料名称"""
        return obj.material.name
    material_name.short_description = '物料名称'

    def subtotal(self, obj):
        """计算小计"""
        return obj.quantity * obj.unit_price
    subtotal.short_description = '小计'
    subtotal.admin_order_field = 'subtotal'

    # 收货状态徽章
    status_badge = create_status_badge_method({
        'pending': '#909399',
        'partial': '#E6A23C',
        'received': '#67C23A',
    })
