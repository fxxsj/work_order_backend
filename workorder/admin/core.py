"""
核心业务 Admin

包含施工单核心业务相关的 admin 类：
- WorkOrderAdmin: 施工单管理
- WorkOrderProcessAdmin: 施工单工序管理
- WorkOrderMaterialAdmin: 施工单物料管理
- ProcessLogAdmin: 流程日志管理
- WorkOrderTaskAdmin: 施工单任务管理

及相关的 Inline 类：
- WorkOrderProductInline: 施工单产品内联
- WorkOrderProcessInline: 施工单工序内联
- WorkOrderMaterialInline: 施工单物料内联
"""
from django.contrib import admin
from django.utils.html import format_html
from ..models import (
    WorkOrder, WorkOrderProcess, WorkOrderMaterial, WorkOrderProduct,
    ProcessLog, WorkOrderTask
)
from .mixins import FixedInlineModelAdminMixin
from .utils import (
    create_status_badge_method,
    create_priority_badge_method,
    WORKORDER_STATUS_COLORS,
    TASK_STATUS_COLORS,
    PURCHASE_STATUS_COLORS,
)


# ==================== Inline 类 ====================

class WorkOrderProcessInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """施工单工序内联"""
    model = WorkOrderProcess
    extra = 1
    fields = ['sequence', 'process', 'status', 'operator',
              'planned_start_time', 'planned_end_time',
              'actual_start_time', 'actual_end_time', 'quantity_completed', 'quantity_defective']


class WorkOrderProductInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """施工单产品内联"""
    model = WorkOrderProduct
    extra = 1
    fields = ['product', 'quantity', 'unit', 'specification', 'sort_order']


class WorkOrderMaterialInline(FixedInlineModelAdminMixin, admin.TabularInline):
    """施工单物料内联"""
    model = WorkOrderMaterial
    extra = 1
    fields = ['material', 'material_size', 'material_usage', 'need_cutting', 'notes',
              'purchase_status', 'purchase_date', 'received_date', 'cut_date']


# ==================== Admin 类 ====================

@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    """施工单管理"""
    list_display = [
        'order_number', 'customer', 'product_name_display',
        'quantity_display', 'status_badge', 'priority_badge',
        'order_date', 'delivery_date', 'progress_bar', 'manager_display'
    ]

    list_filter = [
        'status', 'priority', 'order_date', 'delivery_date',
        'created_at', 'manager'
    ]

    def manager_display(self, obj):
        """制表人显示"""
        return obj.manager.username if obj.manager else '-'
    manager_display.short_description = '制表人'

    def product_name_display(self, obj):
        """显示产品名称（从 products 关联中获取）"""
        products = obj.products.all()
        if products.count() > 1:
            return f'{products.count()}款拼版'
        elif products.count() == 1:
            first_product = products.first()
            return first_product.product.name if first_product.product else '-'
        return '-'
    product_name_display.short_description = '产品'

    def quantity_display(self, obj):
        """显示数量（从 products 关联中计算总和）"""
        products = obj.products.all()
        if products.exists():
            total = sum(p.quantity for p in products)
            return total
        return 0
    quantity_display.short_description = '数量'

    search_fields = [
        'order_number', 'customer__name', 'products__product__name', 'products__product__code'
    ]

    autocomplete_fields = ['customer', 'manager', 'created_by']

    readonly_fields = ['order_number', 'created_at', 'updated_at', 'created_by', 'progress_display']

    date_hierarchy = 'order_date'

    inlines = [WorkOrderProductInline, WorkOrderProcessInline, WorkOrderMaterialInline]

    fieldsets = (
        ('基本信息', {
            'fields': (
                'order_number', 'customer'
            )
        }),
        ('图稿、刀模、烫金版和压凸版', {
            'fields': ('artworks', 'dies', 'foiling_plates', 'embossing_plates'),
            'description': '关联的图稿（CTP版）、刀模（模切）、烫金版和压凸版，支持多个。根据工序选择自动显示和验证。'
        }),
        ('状态与优先级', {
            'fields': ('status', 'priority', 'manager')
        }),
        ('日期信息', {
            'fields': (
                'order_date', 'delivery_date', 'actual_delivery_date',
                'production_quantity', 'defective_quantity'
            )
        }),
        ('财务信息', {
            'fields': ('total_amount',)
        }),
        ('附件', {
            'fields': ('design_file',),
            'classes': ('collapse',)
        }),
        ('其他信息', {
            'fields': ('notes', 'progress_display')
        }),
        ('系统信息', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # 使用工具方法创建状态和优先级徽章
    status_badge = create_status_badge_method(WORKORDER_STATUS_COLORS)
    priority_badge = create_priority_badge_method()

    def save_model(self, request, obj, form, change):
        if not change:  # 如果是新建
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def progress_bar(self, obj):
        """进度条"""
        percentage = obj.get_progress_percentage()
        color = '#67C23A' if percentage == 100 else '#409EFF'
        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; height: 20px; background-color: {}; '
            'border-radius: 3px; text-align: center; color: white; line-height: 20px;">'
            '{}%</div></div>',
            percentage, color, percentage
        )
    progress_bar.short_description = '进度'

    def progress_display(self, obj):
        """进度显示（只读字段）"""
        if obj.pk:
            percentage = obj.get_progress_percentage()
            total = obj.order_processes.count()
            completed = obj.order_processes.filter(status='completed').count()
            return format_html(
                '<div style="font-size: 14px;">'
                '<p>进度: {}% ({}/{})</p>'
                '<div style="width: 200px; background-color: #f0f0f0; '
                'border-radius: 3px; height: 25px;">'
                '<div style="width: {}%; height: 25px; background-color: #409EFF; '
                'border-radius: 3px; text-align: center; color: white; '
                'line-height: 25px;">{}%</div></div></div>',
                percentage, completed, total, percentage, percentage
            )
        return '-'
    progress_display.short_description = '当前进度'

    def get_queryset(self, request):
        """优化查询"""
        qs = super().get_queryset(request)
        return qs.select_related('customer', 'manager', 'created_by').prefetch_related('products__product')


@admin.register(WorkOrderProcess)
class WorkOrderProcessAdmin(admin.ModelAdmin):
    """施工单工序管理"""
    list_display = [
        'work_order', 'sequence', 'process', 'department', 'status_badge',
        'operator', 'actual_start_time', 'actual_end_time',
        'duration_hours', 'quantity_completed', 'quantity_defective'
    ]

    list_filter = [
        'status', 'process', 'department', 'operator',
        'actual_start_time', 'created_at'
    ]

    search_fields = [
        'work_order__order_number', 'process__name',
        'process__code', 'operator__username', 'department__name'
    ]

    autocomplete_fields = ['work_order', 'process', 'operator', 'department']

    readonly_fields = ['created_at', 'updated_at', 'duration_hours']

    date_hierarchy = 'actual_start_time'

    fieldsets = (
        ('基本信息', {
            'fields': ('work_order', 'process', 'department', 'sequence', 'status', 'operator')
        }),
        ('计划时间', {
            'fields': ('planned_start_time', 'planned_end_time')
        }),
        ('实际时间', {
            'fields': ('actual_start_time', 'actual_end_time', 'duration_hours')
        }),
        ('数量统计', {
            'fields': ('quantity_completed', 'quantity_defective')
        }),
        ('其他', {
            'fields': ('notes',)
        }),
        ('系统信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # 工序状态徽章（自定义状态包含 'skipped'）
    status_badge = create_status_badge_method({
        'pending': '#909399',
        'in_progress': '#409EFF',
        'completed': '#67C23A',
        'skipped': '#E6A23C',
    })


@admin.register(WorkOrderMaterial)
class WorkOrderMaterialAdmin(admin.ModelAdmin):
    """施工单物料管理"""
    list_display = [
        'work_order', 'material', 'material_size', 'material_usage',
        'need_cutting', 'notes', 'purchase_status_badge',
        'purchase_date', 'received_date', 'cut_date', 'created_at'
    ]

    list_filter = ['purchase_status', 'need_cutting', 'purchase_date', 'received_date', 'cut_date', 'material', 'created_at']
    search_fields = ['work_order__order_number', 'material__name', 'material__code']
    autocomplete_fields = ['work_order', 'material']

    fieldsets = (
        ('基本信息', {
            'fields': ('work_order', 'material', 'material_size', 'material_usage', 'need_cutting')
        }),
        ('采购和开料状态', {
            'fields': ('purchase_status', 'purchase_date', 'received_date', 'cut_date')
        }),
        ('其他', {
            'fields': ('notes',)
        }),
        ('系统信息', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    # 采购状态徽章（使用预定义的颜色）
    purchase_status_badge = create_status_badge_method({
        'pending': '#909399',
        'ordered': '#409EFF',
        'received': '#67C23A',
        'cut': '#E6A23C',
        'completed': '#67C23A',
    })


@admin.register(ProcessLog)
class ProcessLogAdmin(admin.ModelAdmin):
    """流程日志管理"""
    list_display = [
        'work_order_process', 'log_type_badge',
        'operator', 'content_preview', 'created_at'
    ]

    list_filter = ['log_type', 'created_at', 'operator']
    search_fields = ['work_order_process__work_order__order_number', 'content']
    autocomplete_fields = ['work_order_process', 'operator']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    # 日志类型徽章
    log_type_badge = create_status_badge_method({
        'start': '#409EFF',
        'pause': '#E6A23C',
        'resume': '#67C23A',
        'complete': '#67C23A',
        'note': '#909399',
    })

    def content_preview(self, obj):
        """内容预览"""
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    content_preview.short_description = '内容'


@admin.register(WorkOrderTask)
class WorkOrderTaskAdmin(admin.ModelAdmin):
    """施工单任务管理"""
    list_display = [
        'work_order_process', 'task_type', 'work_content',
        'assigned_department', 'assigned_operator',
        'artwork', 'die', 'product', 'material', 'foiling_plate', 'embossing_plate',
        'production_quantity', 'quantity_completed', 'quantity_defective', 'status_badge', 'created_at'
    ]

    list_filter = [
        'task_type', 'status', 'work_order_process__work_order',
        'work_order_process__process', 'assigned_department', 'assigned_operator',
        'created_at'
    ]

    search_fields = [
        'work_content', 'work_order_process__work_order__order_number',
        'artwork__name', 'artwork__base_code', 'die__code', 'die__name',
        'product__name', 'product__code', 'material__name', 'material__code',
        'foiling_plate__name', 'foiling_plate__code', 'embossing_plate__name', 'embossing_plate__code',
        'assigned_department__name', 'assigned_operator__username', 'assigned_operator__first_name', 'assigned_operator__last_name'
    ]

    autocomplete_fields = ['work_order_process', 'artwork', 'die', 'product', 'material',
                          'foiling_plate', 'embossing_plate', 'assigned_department', 'assigned_operator']

    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('work_order_process', 'task_type', 'work_content', 'status')
        }),
        ('任务分派', {
            'fields': ('assigned_department', 'assigned_operator'),
            'description': '任务分派到哪个部门和操作员。如果未分派，任务生成时会根据工序自动分派。'
        }),
        ('关联对象', {
            'fields': ('artwork', 'die', 'product', 'material', 'foiling_plate', 'embossing_plate'),
            'description': '根据任务类型，关联相应的图稿、刀模、产品、物料、烫金版或压凸版'
        }),
        ('数量信息', {
            'fields': ('production_quantity', 'quantity_completed', 'quantity_defective', 'auto_calculate_quantity')
        }),
        ('系统信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # 任务状态徽章
    status_badge = create_status_badge_method(TASK_STATUS_COLORS)

    def get_queryset(self, request):
        """优化查询"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'work_order_process', 'work_order_process__work_order',
            'work_order_process__process', 'artwork', 'die', 'product', 'material',
            'foiling_plate', 'embossing_plate', 'assigned_department', 'assigned_operator'
        )
