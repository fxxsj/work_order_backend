"""
Django Admin 工具函数和通用方法

此模块提供了 Django Admin 界面中常用的工具函数和混入类，
用于减少代码重复并统一界面样式。
"""

from django.contrib import admin
from django.utils.html import format_html

# ==================== 状态徽章工厂函数 ====================


def create_status_badge_method(
    status_colors,
    default_color="#909399",
    field="status",
    display_method=None,
):
    """
    创建状态徽章显示方法的工厂函数

    Args:
        status_colors: 状态到颜色的映射字典
                      例如: {'pending': '#909399', 'completed': '#67C23A'}
        default_color: 默认颜色（当状态不在映射中时使用）
        field: 读取状态的字段名（默认 "status"）
        display_method: 显示名称的方法名（可选），
                        未提供则尝试使用 get_<field>_display

    Returns:
        一个可以用作 Admin 方法的函数

    Usage:
        class MyModelAdmin(admin.ModelAdmin):
            status_badge = create_status_badge_method({
                'pending': '#909399',
                'completed': '#67C23A',
            })
            list_display = ['name', 'status_badge']
    """

    @admin.display(description="状态")
    def status_badge(self, obj):
        """状态徽章"""
        value = getattr(obj, field, None)
        display = None
        if display_method:
            display_attr = getattr(obj, display_method, None)
            if callable(display_attr):
                display = display_attr()
            elif display_attr is not None:
                display = str(display_attr)
        else:
            display_attr = getattr(obj, f"get_{field}_display", None)
            if callable(display_attr):
                display = display_attr()
        if display is None:
            display = "" if value is None else str(value)
        return format_html(
            '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
            'background-color: {};">{}</span>',
            status_colors.get(value, default_color),
            display,
        )

    return status_badge


def create_priority_badge_method(priority_colors=None, default_color="#409EFF"):
    """
    创建优先级徽章显示方法的工厂函数

    Args:
        priority_colors: 优先级到颜色的映射字典（可选）
        default_color: 默认颜色（当优先级不在映射中时使用）

    Returns:
        一个可以用作 Admin 方法的函数

    Usage:
        class WorkOrderAdmin(admin.ModelAdmin):
            priority_badge = create_priority_badge_method()
            list_display = ['order_number', 'priority_badge']
    """
    if priority_colors is None:
        priority_colors = {
            "low": "#909399",
            "normal": "#409EFF",
            "high": "#E6A23C",
            "urgent": "#F56C6C",
        }

    @admin.display(description="优先级")
    def priority_badge(self, obj):
        """优先级徽章"""
        return format_html(
            '<span style="padding: 3px 8px; border-radius: 3px; color: white; '
            'background-color: {};">{}</span>',
            priority_colors.get(obj.priority, default_color),
            obj.get_priority_display(),
        )

    return priority_badge


# ==================== 预定义的状态颜色配置 ====================

# 施工单状态颜色
WORKORDER_STATUS_COLORS = {
    "pending": "#909399",
    "in_progress": "#409EFF",
    "paused": "#E6A23C",
    "completed": "#67C23A",
    "cancelled": "#F56C6C",
}

# 任务状态颜色
TASK_STATUS_COLORS = {
    "pending": "#909399",
    "in_progress": "#409EFF",
    "completed": "#67C23A",
    "cancelled": "#F56C6C",
    "failed": "#F56C6C",
}

# 库存状态颜色
STOCK_STATUS_COLORS = {
    "in_stock": "#67C23A",
    "reserved": "#E6A23C",
    "quality_check": "#409EFF",
    "defective": "#F56C6C",
}

# 入库/出库单状态颜色
IN_OUT_ORDER_STATUS_COLORS = {
    "draft": "#909399",
    "submitted": "#E6A23C",
    "approved": "#67C23A",
    "rejected": "#F56C6C",
    "confirmed": "#67C23A",
}

# 财务单据状态颜色
FINANCE_STATUS_COLORS = {
    "draft": "#909399",
    "confirmed": "#67C23A",
    "cancelled": "#F56C6C",
    "paid": "#67C23A",
    "unpaid": "#E6A23C",
    "partial": "#409EFF",
}

# 质检状态颜色
QUALITY_STATUS_COLORS = {
    "pending": "#909399",
    "in_progress": "#409EFF",
    "passed": "#67C23A",
    "failed": "#F56C6C",
    "cancelled": "#F56C6C",
}

# 采购状态颜色
PURCHASE_STATUS_COLORS = {
    "draft": "#909399",
    "submitted": "#E6A23C",
    "approved": "#67C23A",
    "rejected": "#F56C6C",
    "in_progress": "#409EFF",
    "completed": "#67C23A",
}


# ==================== 通用显示方法 ====================


def create_foreign_key_display_method(field_name, display_name=None):
    """
    创建外键字段显示方法的工厂函数

    Args:
        field_name: 外键字段名
        display_name: 显示名称（用于 short_description）

    Returns:
        一个可以用作 Admin 方法的函数

    Usage:
        class MyModelAdmin(admin.ModelAdmin):
            customer_name = create_foreign_key_display_method('customer', '客户')
            list_display = ['order_number', 'customer_name']
    """

    @admin.display(description=display_name or field_name.replace("_", " ").title())
    def foreign_key_display(self, obj):
        """显示外键关联对象的名称"""
        foreign_obj = getattr(obj, field_name, None)
        if foreign_obj is None:
            return "-"
        # 尝试获取 name 属性，如果没有则使用 __str__
        return getattr(foreign_obj, "name", str(foreign_obj))

    return foreign_key_display


def create_user_display_method(field_name, display_name=None):
    """
    创建用户字段显示方法的工厂函数

    Args:
        field_name: 用户字段名
        display_name: 显示名称（用于 short_description）

    Returns:
        一个可以用作 Admin 方法的函数

    Usage:
        class MyModelAdmin(admin.ModelAdmin):
            created_by_name = create_user_display_method('created_by', '创建人')
            list_display = ['order_number', 'created_by_name']
    """

    @admin.display(description=display_name or field_name.replace("_", " ").title())
    def user_display(self, obj):
        """显示用户名"""
        user = getattr(obj, field_name, None)
        return user.username if user else "-"

    return user_display


# ==================== Admin Mixin 类 ====================


class TimestampMixin:
    """
    时间戳 Mixin

    为 Admin 类提供标准的时间戳字段显示
    """

    @admin.display(description="创建时间")
    def created_at_display(self, obj):
        """创建时间显示"""
        return obj.created_at.strftime("%Y-%m-%d %H:%M") if obj.created_at else "-"

    @admin.display(description="更新时间")
    def updated_at_display(self, obj):
        """更新时间显示"""
        return obj.updated_at.strftime("%Y-%m-%d %H:%M") if obj.updated_at else "-"


class CreatedByMixin:
    """
    创建人 Mixin

    为 Admin 类提供标准的创建人字段显示
    """

    @admin.display(description="创建人")
    def created_by_display(self, obj):
        """创建人显示"""
        return obj.created_by.username if obj.created_by else "-"


class ReadOnlyMixin:
    """
    只读字段 Mixin

    为 Admin 类提供标准的只读字段配置
    """

    readonly_fields = ["created_at", "updated_at"]


# ==================== 辅助函数 ====================


def get_admin_url(obj, action="change"):
    """
    获取对象的 Admin URL

    Args:
        obj: 模型实例
        action: Admin 动作（change, delete, history 等）

    Returns:
        Admin URL 或 None
    """
    from django.contrib.admin.site import site
    from django.urls import NoReverseMatch, reverse

    try:
        model_admin = site._registry.get(type(obj))
        if model_admin:
            return reverse(
                f"admin:{obj._meta.app_label}_{obj._meta.model_name}_{action}",
                args=[obj.pk],
            )
    except NoReverseMatch:
        pass
    return None


def get_admin_link(obj, text=None):
    """
    获取对象的 Admin 链接 HTML

    Args:
        obj: 模型实例
        text: 链接文本（默认为对象的 __str__）

    Returns:
        HTML 链接字符串或纯文本
    """
    url = get_admin_url(obj)
    if url:
        display_text = text or str(obj)
        return format_html('<a href="{}">{}</a>', url, display_text)
    return str(obj) if obj else "-"
