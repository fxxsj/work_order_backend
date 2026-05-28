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
from django.db.models import Count, Sum
from django.utils.html import format_html

from ..models import (
    Material,
    MaterialStockLog,
    MaterialSupplier,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceiveRecord,
    Supplier,
)
from .mixins import FixedInlineModelAdminMixin
from .utils import PURCHASE_STATUS_COLORS, create_status_badge_method

# ==================== Inline 类 ====================


class PurchaseOrderItemInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """采购单明细内联"""

    model = PurchaseOrderItem
    extra = 1
    fields = [
        "material",
        "quantity",
        "received_quantity",
        "unit_price",
        "status",
        "notes",
    ]
    readonly_fields = ["created_at", "updated_at"]


# ==================== Admin 类 ====================


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    """物料管理"""

    list_display = [
        "code",
        "name",
        "specification",
        "unit",
        "unit_price",
        "stock_quantity",
        "min_stock_quantity",
        "default_supplier",
        "need_cutting",
        "created_at",
    ]
    search_fields = ["code", "name", "specification"]
    list_filter = ["unit", "need_cutting", "default_supplier", "created_at"]
    list_editable = ["unit_price", "stock_quantity"]
    autocomplete_fields = ["default_supplier"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "基本信息",
            {"fields": ("code", "name", "specification", "unit", "unit_price")},
        ),
        (
            "库存信息",
            {
                "fields": ("stock_quantity", "min_stock_quantity"),
                "description": "物料的库存管理信息",
            },
        ),
        (
            "采购信息",
            {
                "fields": ("default_supplier", "lead_time_days", "need_cutting"),
            },
        ),
        ("其他", {"fields": ("notes",)}),
        (
            "系统信息",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    """供应商管理（优化版）"""

    list_display = [
        "code",
        "name",
        "contact_person",
        "phone",
        "email",
        "status",
        "material_count",
        "created_at",
    ]
    search_fields = ["code", "name", "contact_person", "phone", "email"]
    list_filter = ["status", "created_at"]
    list_editable = ["status"]
    ordering = ["code"]
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        """优化查询性能"""
        qs = super().get_queryset(request)
        # 使用注解预计算物料数量
        qs = qs.annotate(_material_count=Count("materialsupplier"))
        return qs

    @admin.display(description="供应物料数", ordering="_material_count")
    def material_count(self, obj):
        """显示供应物料数量（优化版）"""
        return getattr(obj, "_material_count", obj.default_materials.count())


@admin.register(MaterialSupplier)
class MaterialSupplierAdmin(admin.ModelAdmin):
    """物料供应商关联管理"""

    list_display = [
        "material_code",
        "material_name",
        "supplier_code",
        "supplier_name",
        "supplier_price",
        "is_preferred",
        "lead_time_days",
        "min_order_quantity",
    ]
    list_filter = ["is_preferred", "created_at"]
    list_select_related = ["material", "supplier"]
    search_fields = [
        "material__name",
        "material__code",
        "supplier__name",
        "supplier__code",
    ]
    list_editable = [
        "is_preferred",
        "supplier_price",
        "min_order_quantity",
        "lead_time_days",
    ]
    ordering = ["material", "supplier"]
    readonly_fields = ["created_at"]

    @admin.display(description="物料编码")
    def material_code(self, obj):
        """显示物料编码"""
        return obj.material.code
 
    @admin.display(description="物料名称")
    def material_name(self, obj):
        """显示物料名称"""
        return obj.material.name
 
    @admin.display(description="供应商编码")
    def supplier_code(self, obj):
        """显示供应商编码"""
        return obj.supplier.code
 
    @admin.display(description="供应商名称")
    def supplier_name(self, obj):
        """显示供应商名称"""
        return obj.supplier.name


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    """采购单管理（优化版）"""

    list_display = [
        "order_number",
        "supplier_name",
        "status_badge",
        "total_amount",
        "submitted_by_name",
        "approved_by_name",
        "items_count",
        "received_progress",
        "created_at",
    ]
    list_filter = ["status", "supplier", "submitted_at", "approved_at", "created_at"]
    list_select_related = ["supplier", "submitted_by", "approved_by", "work_order"]
    search_fields = ["order_number", "supplier__name", "work_order__order_number"]
    autocomplete_fields = ["supplier", "work_order"]
    readonly_fields = ["order_number", "created_at", "updated_at"]
    ordering = ["-created_at"]
    inlines = [PurchaseOrderItemInline]

    fieldsets = (
        ("基本信息", {"fields": ("order_number", "supplier", "work_order", "status")}),
        (
            "审核信息",
            {"fields": ("submitted_by", "submitted_at", "approved_by", "approved_at")},
        ),
        (
            "采购时间",
            {"fields": ("ordered_date", "expected_date", "actual_received_date")},
        ),
        ("其他信息", {"fields": ("total_amount", "notes", "rejection_reason")}),
        (
            "系统信息",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        """优化查询性能"""
        qs = super().get_queryset(request)
        qs = qs.select_related(
            "supplier", "submitted_by", "approved_by"
        ).prefetch_related("items__material")

        # 使用注解优化items_count和received_progress
        qs = qs.annotate(
            _items_count=Count("items"),
            _total_quantity=Sum("items__quantity"),
            _total_received=Sum("items__received_quantity"),
        )

        return qs

    @admin.display(description="供应商")
    def supplier_name(self, obj):
        """显示供应商名称"""
        return obj.supplier.name
 
    @admin.display(description="提交人")
    def submitted_by_name(self, obj):
        """显示提交人"""
        return obj.submitted_by.username if obj.submitted_by else "-"
 
    @admin.display(description="审核人")
    def approved_by_name(self, obj):
        """显示审核人"""
        return obj.approved_by.username if obj.approved_by else "-"
 
    @admin.display(description="明细数量")
    def items_count(self, obj):
        """显示明细数量（优化版）"""
        return getattr(obj, "_items_count", obj.items.count())
 
    @admin.display(description="收货进度")
    def received_progress(self, obj):
        """显示收货进度（优化版）"""
        # 使用预计算的注解字段
        if hasattr(obj, "_total_quantity") and hasattr(obj, "_total_received"):
            total_quantity = obj._total_quantity or 0
            total_received = obj._total_received or 0
        else:
            # 回退方案
            items = obj.items.all()
            if not items:
                return "-"
            total_quantity = sum(item.quantity for item in items)
            total_received = sum(item.received_quantity for item in items)

        if total_quantity == 0:
            return "0%"

        percentage = round((total_received / total_quantity) * 100, 2)
        color = (
            "#67C23A"
            if percentage >= 100
            else "#409EFF" if percentage >= 50 else "#E6A23C"
        )

        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; height: 20px; background-color: {}; border-radius: 3px; '
            'text-align: center; color: white; line-height: 20px;">{}%</div></div>',
            percentage,
            color,
            percentage,
        )

    # 采购单状态徽章
    status_badge = create_status_badge_method(
        {
            "draft": "#909399",
            "submitted": "#E6A23C",
            "approved": "#409EFF",
            "ordered": "#67C23A",
            "received": "#67C23A",
            "cancelled": "#F56C6C",
        }
    )


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    """采购单明细管理"""

    list_display = [
        "purchase_order_number",
        "material_code",
        "material_name",
        "quantity",
        "received_quantity",
        "unit_price",
        "subtotal",
        "status_badge",
        "created_at",
    ]
    list_filter = ["status", "material", "purchase_order", "created_at"]
    list_select_related = ["purchase_order", "material"]
    search_fields = ["purchase_order__order_number", "material__name", "material__code"]
    autocomplete_fields = ["material", "purchase_order", "work_order_material"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["purchase_order", "id"]

    @admin.display(description="采购单号")
    def purchase_order_number(self, obj):
        """显示采购单号"""
        return obj.purchase_order.order_number
 
    @admin.display(description="物料编码")
    def material_code(self, obj):
        """显示物料编码"""
        return obj.material.code
 
    @admin.display(description="物料名称")
    def material_name(self, obj):
        """显示物料名称"""
        return obj.material.name
 
    @admin.display(description="小计", ordering="subtotal")
    def subtotal(self, obj):
        """计算小计"""
        return obj.quantity * obj.unit_price

    # 收货状态徽章
    status_badge = create_status_badge_method(
        {
            "pending": "#909399",
            "partial": "#E6A23C",
            "received": "#67C23A",
        }
    )


@admin.register(PurchaseReceiveRecord)
class PurchaseReceiveRecordAdmin(admin.ModelAdmin):
    """采购收货记录管理"""

    list_display = [
        "purchase_order_number",
        "material_name",
        "received_quantity",
        "received_date",
        "inspection_status",
        "is_stocked",
        "is_returned",
        "received_by",
    ]
    list_filter = [
        "inspection_status",
        "is_stocked",
        "is_returned",
        "received_date",
        "created_at",
    ]
    search_fields = [
        "purchase_order_item__purchase_order__order_number",
        "purchase_order_item__material__name",
        "purchase_order_item__material__code",
        "delivery_note_number",
    ]
    autocomplete_fields = [
        "purchase_order_item",
        "received_by",
        "inspected_by",
        "stocked_by",
        "returned_by",
    ]
    list_select_related = [
        "purchase_order_item__purchase_order",
        "purchase_order_item__material",
        "received_by",
        "inspected_by",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "inspected_at",
        "stocked_at",
        "returned_at",
    ]
    ordering = ["-received_date", "-created_at"]

    fieldsets = (
        (
            "收货信息",
            {
                "fields": (
                    "purchase_order_item",
                    "received_quantity",
                    "received_date",
                    "received_by",
                    "delivery_note_number",
                )
            },
        ),
        (
            "质检信息",
            {
                "fields": (
                    "inspection_status",
                    "qualified_quantity",
                    "unqualified_quantity",
                    "unqualified_reason",
                    "inspected_by",
                    "inspected_at",
                )
            },
        ),
        (
            "入库与退货",
            {
                "fields": (
                    "is_stocked",
                    "stocked_at",
                    "stocked_by",
                    "is_returned",
                    "returned_quantity",
                    "returned_at",
                    "returned_by",
                    "return_note",
                )
            },
        ),
        ("备注", {"fields": ("notes",)}),
        (
            "系统信息",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="采购单号")
    def purchase_order_number(self, obj):
        return obj.purchase_order.order_number

    @admin.display(description="物料")
    def material_name(self, obj):
        return obj.material.name


@admin.register(MaterialStockLog)
class MaterialStockLogAdmin(admin.ModelAdmin):
    """物料库存变更日志管理"""

    list_display = [
        "material",
        "change_type",
        "quantity",
        "old_quantity",
        "new_quantity",
        "work_order",
        "created_by",
        "created_at",
    ]
    list_filter = ["change_type", "created_at"]
    list_select_related = ["material", "work_order", "created_by"]
    search_fields = ["material__name", "material__code", "reason", "created_by__username"]
    autocomplete_fields = ["material", "work_order", "created_by"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]
