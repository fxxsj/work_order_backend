from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import (
    Customer, Process, Product, Material, WorkOrder, 
    WorkOrderProcess, WorkOrderMaterial, ProcessLog
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_person', 'phone', 'email', 'created_at']
    search_fields = ['name', 'contact_person', 'phone', 'email']
    list_filter = ['created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'contact_person', 'phone', 'email')
        }),
        ('详细信息', {
            'fields': ('address', 'notes')
        }),
        ('系统信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'standard_duration', 'sort_order', 'is_active', 'created_at']
    search_fields = ['code', 'name']
    list_filter = ['is_active', 'created_at']
    list_editable = ['sort_order', 'is_active']
    ordering = ['sort_order', 'code']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'specification', 'unit', 'unit_price', 'is_active', 'created_at']
    search_fields = ['code', 'name', 'specification', 'paper_type']
    list_filter = ['is_active', 'unit', 'paper_type', 'created_at']
    list_editable = ['unit_price', 'is_active']
    ordering = ['code']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'name', 'specification', 'unit', 'unit_price')
        }),
        ('默认主材信息', {
            'fields': ('paper_type', 'paper_weight', 'paper_brand', 'board_thickness'),
            'description': '创建施工单时将自动带入这些默认值'
        }),
        ('默认工艺信息', {
            'fields': ('printing_method', 'surface_treatment', 'post_processing'),
            'description': '创建施工单时将自动带入这些默认值'
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


class WorkOrderMaterialInline(admin.TabularInline):
    model = WorkOrderMaterial
    extra = 1
    fields = ['material', 'planned_quantity', 'actual_quantity', 'notes']
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
    
    inlines = [WorkOrderProcessInline, WorkOrderMaterialInline]
    
    fieldsets = (
        ('基本信息', {
            'fields': (
                'order_number', 'customer', 'product', 'product_name', 
                'specification', 'quantity', 'unit'
            )
        }),
        ('主材信息', {
            'fields': (
                'paper_type', 'paper_weight', 'paper_brand',
                'board_thickness', 'material_notes'
            ),
            'classes': ('collapse',)
        }),
        ('工艺明细', {
            'fields': (
                'printing_method', 'surface_treatment', 
                'post_processing', 'process_notes'
            ),
            'classes': ('collapse',)
        }),
        ('状态与优先级', {
            'fields': ('status', 'priority', 'manager')
        }),
        ('日期信息', {
            'fields': (
                'order_date', 'delivery_date', 'actual_delivery_date'
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
        'work_order', 'sequence', 'process', 'status_badge',
        'operator', 'actual_start_time', 'actual_end_time',
        'duration_hours', 'quantity_completed', 'quantity_defective'
    ]
    
    list_filter = [
        'status', 'process', 'operator', 
        'actual_start_time', 'created_at'
    ]
    
    search_fields = [
        'work_order__order_number', 'process__name', 
        'process__code', 'operator__username'
    ]
    
    autocomplete_fields = ['work_order', 'process', 'operator']
    
    readonly_fields = ['created_at', 'updated_at', 'duration_hours']
    
    date_hierarchy = 'actual_start_time'
    
    fieldsets = (
        ('基本信息', {
            'fields': ('work_order', 'process', 'sequence', 'status', 'operator')
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
        'work_order', 'material', 
        'planned_quantity', 'actual_quantity', 'created_at'
    ]
    
    list_filter = ['material', 'created_at']
    search_fields = ['work_order__order_number', 'material__name', 'material__code']
    autocomplete_fields = ['work_order', 'material']


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

