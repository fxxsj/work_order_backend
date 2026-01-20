"""
基础管理 Admin

包含基础数据相关的 admin 类：
- CustomerAdmin: 客户管理
- DepartmentAdmin: 部门管理（支持树形结构）
- ProcessAdmin: 工序管理
"""
from django.contrib import admin
from ..models import Customer, Department, Process


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """客户管理"""
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
    """部门管理"""
    list_display = ['code', 'name', 'parent', 'get_children_count', 'sort_order', 'is_active', 'created_at']
    search_fields = ['code', 'name']
    list_filter = ['is_active', 'parent', 'created_at']
    list_editable = ['sort_order', 'is_active']
    ordering = ['sort_order', 'code']
    autocomplete_fields = ['parent']
    filter_horizontal = ['processes']

    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'name', 'parent', 'sort_order', 'is_active')
        }),
        ('工序关联', {
            'fields': ('processes',),
            'description': '选择该部门负责的工序'
        }),
        ('系统信息', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['created_at']

    def get_children_count(self, obj):
        """显示子部门数量"""
        if obj.pk:
            return obj.children.count()
        return 0
    get_children_count.short_description = '子部门数'
    get_children_count.admin_order_field = 'children__count'


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    """工序管理"""
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
        # 注意：任务生成规则字段已废弃，任务生成现在基于工序的 code 字段自动匹配
        # ('任务生成规则', {
        #     'fields': ('task_generation_rule',),
        #     'description': '注意：任务生成现在基于工序的 code 字段自动匹配，不再使用此规则字段。此字段保留仅为向后兼容，请勿修改。'
        # }),
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
