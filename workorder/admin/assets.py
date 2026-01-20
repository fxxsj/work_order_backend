"""
资产管理 Admin

包含资产相关的 admin 类：
- ArtworkAdmin: 图稿管理
- DieAdmin: 刀模管理
- FoilingPlateAdmin: 烫金版管理
- EmbossingPlateAdmin: 压凸版管理

及相关的 Inline 类：
- ArtworkProductInline: 图稿产品关联内联
- DieProductInline: 刀模产品关联内联
- FoilingPlateProductInline: 烫金版产品关联内联
- EmbossingPlateProductInline: 压凸版产品关联内联
"""
from django.contrib import admin
from ..models import Artwork, ArtworkProduct, Die, DieProduct, FoilingPlate, FoilingPlateProduct, EmbossingPlate, EmbossingPlateProduct
from .mixins import FixedInlineModelAdminMixin


# ==================== Inline 类 ====================

class ArtworkProductInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """图稿产品关联内联"""
    model = ArtworkProduct
    extra = 1
    fields = ['product', 'imposition_quantity', 'sort_order']


class DieProductInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """刀模产品关联内联"""
    model = DieProduct
    extra = 1
    fields = ['product', 'quantity', 'sort_order']


class FoilingPlateProductInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """烫金版产品关联内联"""
    model = FoilingPlateProduct
    extra = 1
    fields = ['product', 'quantity', 'sort_order']


class EmbossingPlateProductInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """压凸版产品关联内联"""
    model = EmbossingPlateProduct
    extra = 1
    fields = ['product', 'quantity', 'sort_order']


# ==================== Admin 类 ====================

@admin.register(Artwork)
class ArtworkAdmin(admin.ModelAdmin):
    """图稿管理"""
    list_display = ['full_code_display', 'name', 'color_display', 'imposition_size', 'created_at']
    search_fields = ['base_code', 'name', 'imposition_size']
    list_filter = ['created_at', 'version']
    ordering = ['-base_code', '-version']
    readonly_fields = ['base_code', 'version', 'full_code_display', 'created_at', 'updated_at']
    inlines = [ArtworkProductInline]

    fieldsets = (
        ('基本信息', {
            'fields': ('base_code', 'version', 'full_code_display', 'name', 'cmyk_colors', 'other_colors', 'imposition_size')
        }),
        ('其他', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )

    def full_code_display(self, obj):
        """显示完整编码（包含版本号）"""
        if obj.pk:
            return obj.get_full_code()
        return '-'
    full_code_display.short_description = '图稿编码'

    def color_display(self, obj):
        """显示颜色信息，格式：CMK+928C,金色（5色）"""
        parts = []
        total_count = 0

        # CMYK颜色：按照固定顺序C、M、Y、K排列
        if obj.cmyk_colors:
            cmyk_order = ['C', 'M', 'Y', 'K']  # 固定顺序：1C2M3Y4K
            cmyk_sorted = [c for c in cmyk_order if c in obj.cmyk_colors]
            if cmyk_sorted:
                cmyk_str = ''.join(cmyk_sorted)  # 按固定顺序连接，如：CMK
                parts.append(cmyk_str)
                total_count += len(obj.cmyk_colors)

        # 其他颜色：用逗号分隔
        if obj.other_colors:
            other_colors_list = [c.strip() for c in obj.other_colors if c and c.strip()]
            if other_colors_list:
                other_colors_str = ','.join(other_colors_list)  # 用逗号分隔
                parts.append(other_colors_str)
                total_count += len(other_colors_list)

        # 组合显示：如果有CMYK和其他颜色，用+号连接
        if len(parts) > 1:
            result = '+'.join(parts)
        elif len(parts) == 1:
            result = parts[0]
        else:
            return '-'

        # 添加色数统计
        if total_count > 0:
            result += f'（{total_count}色）'

        return result
    color_display.short_description = '色数'

    def save_model(self, request, obj, form, change):
        """保存时自动生成主编码"""
        if not obj.base_code:
            obj.base_code = Artwork.generate_base_code()
        # 如果是新建且指定了 base_code，自动获取下一个版本号
        if obj.base_code and not change and not obj.version:
            obj.version = Artwork.get_next_version(obj.base_code)
        super().save_model(request, obj, form, change)


@admin.register(Die)
class DieAdmin(admin.ModelAdmin):
    """刀模管理"""
    list_display = ['code', 'name', 'size', 'material', 'thickness', 'created_at']
    search_fields = ['code', 'name', 'size', 'material']
    list_filter = ['material', 'created_at']
    ordering = ['-created_at']
    readonly_fields = ['code', 'created_at', 'updated_at']
    inlines = [DieProductInline]

    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'name', 'size', 'material', 'thickness')
        }),
        ('其他', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        """保存时自动生成编码"""
        if not obj.code:
            obj.code = Die.generate_code()
        super().save_model(request, obj, form, change)


@admin.register(FoilingPlate)
class FoilingPlateAdmin(admin.ModelAdmin):
    """烫金版管理"""
    list_display = ['code', 'name', 'foiling_type', 'size', 'material', 'thickness', 'created_at']
    search_fields = ['code', 'name', 'size', 'material']
    list_filter = ['foiling_type', 'material', 'created_at']
    ordering = ['-created_at']
    readonly_fields = ['code', 'created_at', 'updated_at']
    inlines = [FoilingPlateProductInline]

    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'name', 'foiling_type', 'size', 'material', 'thickness')
        }),
        ('其他', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        """保存时自动生成编码"""
        if not obj.code:
            obj.code = FoilingPlate.generate_code()
        super().save_model(request, obj, form, change)


@admin.register(EmbossingPlate)
class EmbossingPlateAdmin(admin.ModelAdmin):
    """压凸版管理"""
    list_display = ['code', 'name', 'size', 'material', 'thickness', 'created_at']
    search_fields = ['code', 'name', 'size', 'material']
    list_filter = ['material', 'created_at']
    ordering = ['-created_at']
    readonly_fields = ['code', 'created_at', 'updated_at']
    inlines = [EmbossingPlateProductInline]

    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'name', 'size', 'material', 'thickness')
        }),
        ('其他', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        """保存时自动生成编码"""
        if not obj.code:
            obj.code = EmbossingPlate.generate_code()
        super().save_model(request, obj, form, change)
