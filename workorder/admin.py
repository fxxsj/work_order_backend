from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import (
    Customer, Department, Process, Product, ProductMaterial, Material, WorkOrder,
    WorkOrderProcess, WorkOrderMaterial, WorkOrderProduct, ProcessLog, Artwork, ArtworkProduct,
    Die, DieProduct, FoilingPlate, FoilingPlateProduct, EmbossingPlate, EmbossingPlateProduct,
    WorkOrderTask, ProductGroup, ProductGroupItem, UserProfile
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
    list_display = ['code', 'name', 'is_builtin', 'standard_duration', 'sort_order', 'is_active', 'created_at']
    search_fields = ['code', 'name']
    list_filter = ['is_builtin', 'is_active', 'created_at']
    list_editable = ['sort_order', 'is_active']
    ordering = ['sort_order', 'code']
    readonly_fields = ['is_builtin', 'created_at']  # is_builtin字段只读
    
    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'name', 'description', 'standard_duration', 'sort_order', 'is_active', 'is_builtin')
        }),
        ('任务生成规则', {
            'fields': ('task_generation_rule',),
            'description': '该工序如何生成任务'
        }),
        ('工序与版的关系配置', {
            'fields': (
                ('requires_artwork', 'artwork_required'),
                ('requires_die', 'die_required'),
                ('requires_foiling_plate', 'foiling_plate_required'),
                ('requires_embossing_plate', 'embossing_plate_required'),
            ),
            'description': '配置该工序需要哪些版，以及版是否必选。如果版必选，选择该工序时必须选择对应的版；如果版可选，未选择时将生成设计任务。'
        }),
        ('系统信息', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """根据is_builtin字段动态设置code字段为只读"""
        readonly = list(self.readonly_fields)
        if obj and obj.is_builtin:
            # 内置工序的code字段不可编辑
            readonly.append('code')
        return readonly
    
    def has_delete_permission(self, request, obj=None):
        """内置工序不可删除"""
        if obj and obj.is_builtin:
            return False
        return super().has_delete_permission(request, obj)
    
    def get_queryset(self, request):
        """优化查询"""
        return super().get_queryset(request).select_related()


class ProductMaterialInline(admin.TabularInline):
    model = ProductMaterial
    extra = 1
    fields = ['material', 'material_size', 'material_usage', 'need_cutting', 'notes', 'sort_order']
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
    fields = ['material', 'material_size', 'material_usage', 'need_cutting', 'notes', 
              'purchase_status', 'purchase_date', 'received_date', 'cut_date']
    autocomplete_fields = ['material']


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
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
        return qs.select_related('customer', 'manager', 'created_by').prefetch_related('products__product')


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


class FoilingPlateProductInline(admin.TabularInline):
    model = FoilingPlateProduct
    extra = 1
    fields = ['product', 'quantity', 'sort_order']
    autocomplete_fields = ['product']


@admin.register(FoilingPlate)
class FoilingPlateAdmin(admin.ModelAdmin):
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


class EmbossingPlateProductInline(admin.TabularInline):
    model = EmbossingPlateProduct
    extra = 1
    fields = ['product', 'quantity', 'sort_order']
    autocomplete_fields = ['product']


@admin.register(EmbossingPlate)
class EmbossingPlateAdmin(admin.ModelAdmin):
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


@admin.register(WorkOrderTask)
class WorkOrderTaskAdmin(admin.ModelAdmin):
    """施工单任务管理"""
    list_display = [
        'work_order_process', 'task_type', 'work_content', 
        'artwork', 'die', 'product', 'material',
        'production_quantity', 'quantity_completed', 'status_badge', 'created_at'
    ]
    
    list_filter = [
        'task_type', 'status', 'work_order_process__work_order', 
        'work_order_process__process', 'created_at'
    ]
    
    search_fields = [
        'work_content', 'work_order_process__work_order__order_number',
        'artwork__name', 'artwork__base_code', 'die__code', 'die__name',
        'product__name', 'product__code', 'material__name', 'material__code'
    ]
    
    autocomplete_fields = ['work_order_process', 'artwork', 'die', 'product', 'material']
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('work_order_process', 'task_type', 'work_content', 'status')
        }),
        ('关联对象', {
            'fields': ('artwork', 'die', 'product', 'material'),
            'description': '根据任务类型，关联相应的图稿、刀模、产品或物料'
        }),
        ('数量信息', {
            'fields': ('production_quantity', 'quantity_completed', 'auto_calculate_quantity')
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
            'cancelled': '#F56C6C',
        }
        return format_html(
            '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
            'background-color: {};">{}</span>',
            colors.get(obj.status, '#909399'),
            obj.get_status_display()
        )
    status_badge.short_description = '状态'
    
    def get_queryset(self, request):
        """优化查询"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'work_order_process', 'work_order_process__work_order',
            'work_order_process__process', 'artwork', 'die', 'product', 'material'
        )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """用户扩展信息管理"""
    list_display = ['user', 'department', 'created_at']
    list_filter = ['department', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'department__name']
    raw_id_fields = ['user', 'department']
    ordering = ['-created_at']

