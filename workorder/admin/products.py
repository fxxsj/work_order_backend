"""
产品管理 Admin

包含产品相关的 admin 类：
- ProductAdmin: 产品管理
- ProductGroupAdmin: 产品组管理

及相关的 Inline 类：
- ProductMaterialInline: 产品物料关联内联
"""
from django.contrib import admin
from ..models import Product, ProductGroup, ProductGroupItem, ProductMaterial
from .mixins import FixedInlineModelAdminMixin


# ==================== Inline 类 ====================

class ProductMaterialInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """产品物料关联内联"""
    model = ProductMaterial
    extra = 1
    fields = ['material', 'material_size', 'material_usage', 'need_cutting', 'notes', 'sort_order']


# ==================== Admin 类 ====================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """产品管理"""
    list_display = ['code', 'name', 'specification', 'unit', 'unit_price',
                    'stock_quantity', 'min_stock_quantity', 'is_active', 'created_at']
    search_fields = ['code', 'name', 'specification']
    list_filter = ['is_active', 'unit', 'created_at']
    list_editable = ['unit_price', 'stock_quantity', 'min_stock_quantity', 'is_active']
    ordering = ['code']
    filter_horizontal = ['default_processes']
    inlines = [ProductMaterialInline]

    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'name', 'specification', 'unit', 'unit_price')
        }),
        ('库存信息', {
            'fields': ('stock_quantity', 'min_stock_quantity'),
            'description': '产品的库存管理信息'
        }),
        ('默认工序', {
            'fields': ('default_processes',),
            'description': '创建施工单时将自动添加这些工序'
        }),
        ('其他', {
            'fields': ('description', 'is_active')
        }),
    )


@admin.register(ProductGroup)
class ProductGroupAdmin(admin.ModelAdmin):
    """产品组管理"""
    list_display = ['name', 'description', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    list_filter = ['is_active', 'created_at']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('系统信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProductGroupItem)
class ProductGroupItemAdmin(admin.ModelAdmin):
    """产品组项目管理"""
    list_display = ['product_group', 'product', 'item_name', 'sort_order', 'created_at']
    list_filter = ['product_group', 'created_at']
    search_fields = ['product_group__name', 'product__name', 'product__code', 'item_name']
    autocomplete_fields = ['product_group', 'product']
    list_editable = ['item_name', 'sort_order']
    ordering = ['product_group', 'sort_order']
    readonly_fields = ['created_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('product_group', 'product', 'item_name', 'sort_order')
        }),
        ('系统信息', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
