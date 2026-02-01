"""
系统管理 Admin

包含系统管理相关的 admin 类：
- UserProfileAdmin: 用户扩展信息管理
- WorkOrderApprovalLogAdmin: 施工单审核历史管理
- NotificationAdmin: 通知管理
- TaskAssignmentRuleAdmin: 任务分派规则管理
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta
from ..models import UserProfile, WorkOrderApprovalLog, Notification, TaskAssignmentRule


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """用户扩展信息管理"""
    list_display = ['user', 'get_departments_display', 'created_at']
    list_filter = ['departments', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'departments__name']
    autocomplete_fields = ['user']
    filter_horizontal = ['departments']
    ordering = ['-created_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('user', 'departments')
        }),
        ('系统信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['created_at', 'updated_at']

    def get_departments_display(self, obj):
        """显示部门名称列表"""
        if obj.pk:
            departments = obj.departments.all()
            if departments.exists():
                return ', '.join([dept.name for dept in departments])
        return '-'
    get_departments_display.short_description = '所属部门'


@admin.register(WorkOrderApprovalLog)
class WorkOrderApprovalLogAdmin(admin.ModelAdmin):
    """施工单审核历史管理"""
    list_display = [
        'work_order', 'approval_status_badge', 'approved_by',
        'approved_at', 'has_comment', 'has_rejection_reason'
    ]
    list_filter = ['approval_status', 'approved_at', 'approved_by']
    search_fields = ['work_order__order_number', 'approval_comment', 'rejection_reason']
    readonly_fields = ['created_at', 'approved_at']
    ordering = ['-approved_at', '-created_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('work_order', 'approval_status', 'approved_by', 'approved_at')
        }),
        ('审核内容', {
            'fields': ('approval_comment', 'rejection_reason')
        }),
        ('系统信息', {
            'fields': ('created_at',)
        }),
    )

    def approval_status_badge(self, obj):
        """审核状态徽章"""
        colors = {
            'pending': 'orange',
            'approved': 'green',
            'rejected': 'red'
        }
        color = colors.get(obj.approval_status, 'gray')
        status_display = obj.get_approval_status_display()
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, status_display
        )
    approval_status_badge.short_description = '审核状态'

    def has_comment(self, obj):
        """是否有审核意见"""
        return '是' if obj.approval_comment else '否'
    has_comment.short_description = '有审核意见'

    def has_rejection_reason(self, obj):
        """是否有拒绝原因"""
        return '是' if obj.rejection_reason else '否'
    has_rejection_reason.short_description = '有拒绝原因'


@admin.register(TaskAssignmentRule)
class TaskAssignmentRuleAdmin(admin.ModelAdmin):
    """任务分派规则管理"""
    list_display = [
        'process', 'department', 'priority', 'operator_selection_strategy_display',
        'is_active_badge', 'notes', 'created_at', 'updated_at'
    ]
    list_filter = ['is_active', 'operator_selection_strategy', 'created_at']
    search_fields = ['process__name', 'process__code', 'department__name', 'department__code', 'notes']
    autocomplete_fields = ['process', 'department']
    ordering = ['process', '-priority', 'department']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('process', 'department', 'priority', 'is_active')
        }),
        ('操作员选择策略', {
            'fields': ('operator_selection_strategy',),
            'description': '从部门中选择操作员的策略'
        }),
        ('备注', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('系统信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def is_active_badge(self, obj):
        """显示启用状态"""
        if obj.is_active:
            return format_html('<span style="color: #67C23A;">✓ 启用</span>')
        else:
            return format_html('<span style="color: #909399;">✗ 禁用</span>')
    is_active_badge.short_description = '状态'

    def operator_selection_strategy_display(self, obj):
        """显示操作员选择策略"""
        return obj.get_operator_selection_strategy_display()
    operator_selection_strategy_display.short_description = '操作员选择策略'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """通知管理"""
    list_display = ['recipient', 'title', 'notification_type', 'priority', 'is_read', 'created_at']
    list_filter = ['notification_type', 'priority', 'is_read', 'created_at']
    search_fields = ['recipient__username', 'title', 'content']
    readonly_fields = ['created_at', 'read_at']
    ordering = ['-created_at']
    actions = ['delete_old_notifications']

    fieldsets = (
        ('基本信息', {
            'fields': ('recipient', 'title', 'notification_type', 'priority', 'is_read')
        }),
        ('内容', {
            'fields': ('content',)
        }),
        ('关联对象', {
            'fields': ('work_order', 'work_order_process', 'task', 'purchase_order')
        }),
        ('时间信息', {
            'fields': ('read_at', 'expires_at')
        }),
        ('系统信息', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """过滤30天前的通知（超级用户可以看到所有通知）"""
        qs = super().get_queryset(request)
        # 超级用户可以看到所有通知，其他用户只看到最近30天的通知
        if not request.user.is_superuser:
            thirty_days_ago = timezone.now() - timedelta(days=30)
            return qs.filter(created_at__gte=thirty_days_ago)
        return qs

    def delete_old_notifications(self, request, queryset):
        """批量删除30天前的通知"""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        old_notifications = queryset.filter(created_at__lt=thirty_days_ago)
        count = old_notifications.count()
        old_notifications.delete()
        self.message_user(request, f'{count} 条30天前的通知已删除。')
    delete_old_notifications.short_description = '删除30天前的通知'
