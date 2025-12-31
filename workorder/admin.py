from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import (
    Customer, Department, Process, Product, ProductMaterial, Material, WorkOrder, 
    WorkOrderProcess, WorkOrderMaterial, WorkOrderProduct, ProcessLog, Artwork, ArtworkProduct,
    Die, DieProduct, WorkOrderTask, ProductGroup, ProductGroupItem
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_person', 'phone', 'email', 'salesperson', 'created_at']
    search_fields = ['name', 'contact_person', 'phone', 'email', 'salesperson__username']
    list_filter = ['created_at', 'salesperson']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['salesperson']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'contact_person', 'phone', 'email')
        }),
        ('业务信息', {
            'fields': ('salesperson',)
        }),
        ('详细信息', {
            'fields': ('address', 'notes')
        }),
        ('系统信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'sort_order', 'is_active', 'created_at']
    search_fields = ['code', 'name']
    list_filter = ['is_active', 'created_at']
    list_editable = ['sort_order', 'is_active']
    ordering = ['sort_order', 'code']


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'standard_duration', 'sort_order', 'is_active', 'created_at']
    search_fields = ['code', 'name']
    list_filter = ['is_active', 'created_at']
    list_editable = ['sort_order', 'is_active']
    ordering = ['sort_order', 'code']


class ProductMaterialInline(admin.TabularInline):
    model = ProductMaterial
    extra = 1
    fields = ['material', 'material_size', 'material_usage', 'sort_order']
    autocomplete_fields = ['material']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'specification', 'unit', 'unit_price', 'is_active', 'created_at']
    search_fields = ['code', 'name', 'specification']
    list_filter = ['is_active', 'unit', 'created_at']
    list_editable = ['unit_price', 'is_active']
    ordering = ['code']
    filter_horizontal = ['default_processes']
    inlines = [ProductMaterialInline]
    
    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'name', 'specification', 'unit', 'unit_price')
        }),
        ('默认工序', {
            'fields': ('default_processes',),
            'description': '创建施工单时将自动添加这些工序'
        }),
        ('其他', {
            'fields': ('description', 'is_active')
        }),
    )


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'specification', 'unit', 'unit_price', 
                    'stock_quantity', 'created_at']
    search_fields = ['code', 'name', 'specification']
    list_filter = ['unit', 'created_at']
    list_editable = ['unit_price', 'stock_quantity']


class WorkOrderProcessInline(admin.TabularInline):
    model = WorkOrderProcess
    extra = 1
    fields = ['sequence', 'process', 'status', 'operator', 
              'planned_start_time', 'planned_end_time',
              'actual_start_time', 'actual_end_time', 'quantity_completed']
    autocomplete_fields = ['process', 'operator']


class WorkOrderProductInline(admin.TabularInline):
    model = WorkOrderProduct
    extra = 1
    autocomplete_fields = ['product']
    fields = ['product', 'quantity', 'unit', 'specification', 'sort_order']


class WorkOrderMaterialInline(admin.TabularInline):
    model = WorkOrderMaterial
    extra = 1
    fields = ['material', 'material_size', 'material_usage', 'planned_quantity', 'actual_quantity', 'notes']
    autocomplete_fields = ['material']


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'customer', 'product_name', 
        'quantity', 'status_badge', 'priority_badge',
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
    
    search_fields = [
        'order_number', 'customer__name', 'product_name', 'specification'
    ]
    
    autocomplete_fields = ['customer', 'manager', 'created_by']
    
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'progress_display']
    
    date_hierarchy = 'order_date'
    
    inlines = [WorkOrderProductInline, WorkOrderProcessInline, WorkOrderMaterialInline]
    
    fieldsets = (
        ('基本信息', {
            'fields': (
                'order_number', 'customer', 'product', 'product_name', 
                'specification', 'quantity', 'unit'
            )
        }),
        ('图稿和刀模', {
            'fields': ('artworks', 'dies'),
            'description': '关联的图稿（CTP版）和刀模（模切），支持多个图稿和多个刀模'
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
    
    def save_model(self, request, obj, form, change):
        if not change:  # 如果是新建
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def status_badge(self, obj):
        """状态徽章"""
        colors = {
            'pending': '#909399',
            'in_progress': '#409EFF',
            'paused': '#E6A23C',
            'completed': '#67C23A',
            'cancelled': '#F56C6C',
        }
        return format_html(
            '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
            'background-color: {};">{}</span>',
            colors.get(obj.status, '#909399'),
            obj.get_status_display()
        )
    status_badge.short_description = '状态'
    
    def priority_badge(self, obj):
        """优先级徽章"""
        colors = {
            'low': '#909399',
            'normal': '#409EFF',
            'high': '#E6A23C',
            'urgent': '#F56C6C',
        }
        return format_html(
            '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
            'background-color: {};">{}</span>',
            colors.get(obj.priority, '#409EFF'),
            obj.get_priority_display()
        )
    priority_badge.short_description = '优先级'
    
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
        return qs.select_related('customer', 'manager', 'created_by')


@admin.register(WorkOrderProcess)
class WorkOrderProcessAdmin(admin.ModelAdmin):
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
    
    def status_badge(self, obj):
        """状态徽章"""
        colors = {
            'pending': '#909399',
            'in_progress': '#409EFF',
            'completed': '#67C23A',
            'skipped': '#E6A23C',
        }
        return format_html(
            '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
            'background-color: {};">{}</span>',
            colors.get(obj.status, '#909399'),
            obj.get_status_display()
        )
    status_badge.short_description = '状态'


@admin.register(WorkOrderMaterial)
class WorkOrderMaterialAdmin(admin.ModelAdmin):
    list_display = [
        'work_order', 'material', 'material_size', 'material_usage',
        'notes', 'purchase_status_badge',
        'purchase_date', 'received_date', 'cut_date', 'created_at'
    ]
    
    list_filter = ['purchase_status', 'purchase_date', 'received_date', 'cut_date', 'material', 'created_at']
    search_fields = ['work_order__order_number', 'material__name', 'material__code']
    autocomplete_fields = ['work_order', 'material']
    
    def purchase_status_badge(self, obj):
        """采购状态徽章"""
        colors = {
            'pending': '#909399',
            'ordered': '#409EFF',
            'received': '#67C23A',
            'cut': '#E6A23C',
            'completed': '#67C23A',
        }
        return format_html(
            '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
            'background-color: {};">{}</span>',
            colors.get(obj.purchase_status, '#909399'),
            obj.get_purchase_status_display()
        )
    purchase_status_badge.short_description = '采购状态'


@admin.register(ProcessLog)
class ProcessLogAdmin(admin.ModelAdmin):
    list_display = [
        'work_order_process', 'log_type_badge', 
        'operator', 'content_preview', 'created_at'
    ]
    
    list_filter = ['log_type', 'created_at', 'operator']
    search_fields = ['work_order_process__work_order__order_number', 'content']
    autocomplete_fields = ['work_order_process', 'operator']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def log_type_badge(self, obj):
        """日志类型徽章"""
        colors = {
            'start': '#409EFF',
            'pause': '#E6A23C',
            'resume': '#67C23A',
            'complete': '#67C23A',
            'note': '#909399',
        }
        return format_html(
            '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
            'background-color: {};">{}</span>',
            colors.get(obj.log_type, '#909399'),
            obj.get_log_type_display()
        )
    log_type_badge.short_description = '类型'
    
    def content_preview(self, obj):
        """内容预览"""
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    content_preview.short_description = '内容'


class ArtworkProductInline(admin.TabularInline):
    model = ArtworkProduct
    extra = 1
    fields = ['product', 'imposition_quantity', 'sort_order']
    autocomplete_fields = ['product']


@admin.register(Artwork)
class ArtworkAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'color_count', 'imposition_size', 'created_at']
    search_fields = ['code', 'name', 'imposition_size']
    list_filter = ['color_count', 'created_at']
    ordering = ['-created_at']
    readonly_fields = ['code', 'created_at', 'updated_at']
    inlines = [ArtworkProductInline]
    
    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'name', 'color_count', 'imposition_size')
        }),
        ('其他', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """保存时自动生成编码"""
        if not obj.code:
            obj.code = Artwork.generate_code()
        super().save_model(request, obj, form, change)


class DieProductInline(admin.TabularInline):
    model = DieProduct
    extra = 1
    fields = ['product', 'quantity', 'sort_order']
    autocomplete_fields = ['product']


@admin.register(Die)
class DieAdmin(admin.ModelAdmin):
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

