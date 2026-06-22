"""
资产管理 Admin

包含资产相关的 admin 类：
- ArtworkAdmin: 图稿管理
- DieAdmin: 刀模管理
- FoilingPlateAdmin: 烫金版管理
- EmbossingPlateAdmin: 压凸版管理

及相关的 Inline 类：
- ArtworkImageInline: 图稿图片内联
- ArtworkProductInline: 图稿产品关联内联
- DieImageInline: 刀模图片内联
- DieProductInline: 刀模产品关联内联
- FoilingPlateImageInline: 烫金版图片内联
- FoilingPlateProductInline: 烫金版产品关联内联
- EmbossingPlateImageInline: 压凸版图片内联
- EmbossingPlateProductInline: 压凸版产品关联内联
"""

from django.contrib import admin
from django.utils.html import format_html

from ..models import (
    Artwork,
    ArtworkImage,
    ArtworkProduct,
    Die,
    DieImage,
    DieProduct,
    EmbossingPlate,
    EmbossingPlateImage,
    EmbossingPlateProduct,
    FoilingPlate,
    FoilingPlateImage,
    FoilingPlateProduct,
)
from .mixins import FixedInlineModelAdminMixin

# ==================== Inline 类 ====================


class AssetImageInlineMixin(FixedInlineModelAdminMixin):
    """资产图片内联公共配置"""

    extra = 1
    fields = ["image", "description", "sort_order"]


class ArtworkImageInline(AssetImageInlineMixin, admin.TabularInline):
    """图稿图片内联"""

    model = ArtworkImage


class ArtworkProductInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """图稿产品关联内联"""

    model = ArtworkProduct
    extra = 1
    fields = ["product", "imposition_quantity", "sort_order"]


class DieImageInline(AssetImageInlineMixin, admin.TabularInline):
    """刀模图片内联"""

    model = DieImage


class DieProductInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """刀模产品关联内联"""

    model = DieProduct
    extra = 1
    fields = ["product", "quantity", "relation_type", "sort_order"]


class FoilingPlateImageInline(AssetImageInlineMixin, admin.TabularInline):
    """烫金版图片内联"""

    model = FoilingPlateImage


class FoilingPlateProductInline(
    FixedInlineModelAdminMixin, admin.TabularInline
):
    """烫金版产品关联内联"""

    model = FoilingPlateProduct
    extra = 1
    fields = ["product", "quantity", "sort_order"]


class EmbossingPlateImageInline(AssetImageInlineMixin, admin.TabularInline):
    """压凸版图片内联"""

    model = EmbossingPlateImage


class EmbossingPlateProductInline(
    FixedInlineModelAdminMixin, admin.TabularInline
):
    """压凸版产品关联内联"""

    model = EmbossingPlateProduct
    extra = 1
    fields = ["product", "quantity", "sort_order"]


# ==================== Admin 类 ====================


@admin.display(description="确认状态")
def confirmed_badge(obj):
    """确认状态徽章（供资产 Admin 复用）"""
    if obj.confirmed:
        return format_html(
            '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
            'background-color: #67C23A;">已确认</span>'
        )
    return format_html(
        '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
        'background-color: #909399;">待确认</span>'
    )


@admin.register(Artwork)
class ArtworkAdmin(admin.ModelAdmin):
    """图稿管理"""

    list_display = [
        "full_code_display",
        "name",
        "color_display",
        "imposition_size",
        "confirmed_badge",
        "created_at",
    ]
    search_fields = ["base_code", "name", "imposition_size"]
    list_filter = ["confirmed", "created_at", "version"]
    ordering = ["-base_code", "-version"]
    readonly_fields = [
        "base_code",
        "version",
        "full_code_display",
        "created_at",
        "updated_at",
    ]
    inlines = [ArtworkImageInline, ArtworkProductInline]

    fieldsets = (
        (
            "基本信息",
            {
                "fields": (
                    "base_code",
                    "version",
                    "full_code_display",
                    "name",
                    "cmyk_colors",
                    "other_colors",
                    "imposition_size",
                )
            },
        ),
        (
            "关联版材",
            {
                "fields": ("dies", "foiling_plates", "embossing_plates"),
                "classes": ("collapse",),
            },
        ),
        (
            "确认状态",
            {"fields": ("confirmed", "confirmed_by", "confirmed_at")},
        ),
        ("其他", {"fields": ("notes", "created_at", "updated_at")}),
    )

    confirmed_badge = confirmed_badge

    @admin.display(description="图稿编码")
    def full_code_display(self, obj):
        """显示完整编码（包含版本号）"""
        if obj.pk:
            return obj.get_full_code()
        return "-"

    @admin.display(description="色数")
    def color_display(self, obj):
        """显示颜色信息，格式：CMK+928C,金色（5色）"""
        parts = []
        total_count = 0

        # CMYK颜色：按照固定顺序C、M、Y、K排列
        if obj.cmyk_colors:
            cmyk_order = ["C", "M", "Y", "K"]  # 固定顺序：1C2M3Y4K
            cmyk_sorted = [c for c in cmyk_order if c in obj.cmyk_colors]
            if cmyk_sorted:
                cmyk_str = "".join(cmyk_sorted)  # 按固定顺序连接，如：CMK
                parts.append(cmyk_str)
                total_count += len(obj.cmyk_colors)

        # 其他颜色：用逗号分隔
        if obj.other_colors:
            other_colors_list = [
                c.strip() for c in obj.other_colors if c and c.strip()
            ]
            if other_colors_list:
                other_colors_str = ",".join(other_colors_list)  # 用逗号分隔
                parts.append(other_colors_str)
                total_count += len(other_colors_list)

        # 组合显示：如果有CMYK和其他颜色，用+号连接
        if len(parts) > 1:
            result = "+".join(parts)
        elif len(parts) == 1:
            result = parts[0]
        else:
            return "-"

        # 添加色数统计
        if total_count > 0:
            result += f"（{total_count}色）"

        return result

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

    list_display = [
        "code",
        "name",
        "die_type",
        "size",
        "material",
        "thickness",
        "confirmed_badge",
        "created_at",
    ]
    search_fields = ["code", "name", "size", "material"]
    list_filter = ["die_type", "material", "confirmed", "created_at"]
    ordering = ["-created_at"]
    readonly_fields = ["code", "created_at", "updated_at"]
    inlines = [DieImageInline, DieProductInline]

    fieldsets = (
        (
            "基本信息",
            {
                "fields": (
                    "code",
                    "name",
                    "die_type",
                    "size",
                    "material",
                    "thickness",
                )
            },
        ),
        (
            "确认状态",
            {"fields": ("confirmed", "confirmed_by", "confirmed_at")},
        ),
        ("其他", {"fields": ("notes", "created_at", "updated_at")}),
    )

    confirmed_badge = confirmed_badge

    def save_model(self, request, obj, form, change):
        """保存时自动生成编码"""
        if not obj.code:
            obj.code = Die.generate_code()
        super().save_model(request, obj, form, change)


@admin.register(FoilingPlate)
class FoilingPlateAdmin(admin.ModelAdmin):
    """烫金版管理"""

    list_display = [
        "code",
        "name",
        "foiling_type",
        "size",
        "material",
        "thickness",
        "confirmed_badge",
        "created_at",
    ]
    search_fields = ["code", "name", "size", "material"]
    list_filter = ["foiling_type", "material", "confirmed", "created_at"]
    ordering = ["-created_at"]
    readonly_fields = ["code", "created_at", "updated_at"]
    inlines = [FoilingPlateImageInline, FoilingPlateProductInline]

    fieldsets = (
        (
            "基本信息",
            {
                "fields": (
                    "code",
                    "name",
                    "foiling_type",
                    "size",
                    "material",
                    "thickness",
                )
            },
        ),
        (
            "确认状态",
            {"fields": ("confirmed", "confirmed_by", "confirmed_at")},
        ),
        ("其他", {"fields": ("notes", "created_at", "updated_at")}),
    )

    confirmed_badge = confirmed_badge

    def save_model(self, request, obj, form, change):
        """保存时自动生成编码"""
        if not obj.code:
            obj.code = FoilingPlate.generate_code()
        super().save_model(request, obj, form, change)


@admin.register(EmbossingPlate)
class EmbossingPlateAdmin(admin.ModelAdmin):
    """压凸版管理"""

    list_display = [
        "code",
        "name",
        "size",
        "material",
        "thickness",
        "confirmed_badge",
        "created_at",
    ]
    search_fields = ["code", "name", "size", "material"]
    list_filter = ["material", "confirmed", "created_at"]
    ordering = ["-created_at"]
    readonly_fields = ["code", "created_at", "updated_at"]
    inlines = [EmbossingPlateImageInline, EmbossingPlateProductInline]

    fieldsets = (
        (
            "基本信息",
            {"fields": ("code", "name", "size", "material", "thickness")},
        ),
        (
            "确认状态",
            {"fields": ("confirmed", "confirmed_by", "confirmed_at")},
        ),
        ("其他", {"fields": ("notes", "created_at", "updated_at")}),
    )

    confirmed_badge = confirmed_badge

    def save_model(self, request, obj, form, change):
        """保存时自动生成编码"""
        if not obj.code:
            obj.code = EmbossingPlate.generate_code()
        super().save_model(request, obj, form, change)
