"""
权限相关常量定义

此模块定义了系统权限相关的常量。
"""

from django.utils.translation import gettext_lazy as _


class UserRole:
    """用户角色常量"""

    ADMIN = '系统管理员'
    MANAGER = '经理'
    SUPERVISOR = '主管'
    OPERATOR = '操作员'
    SALESPERSON = '业务员'
    FINANCE = '财务'
    WAREHOUSE = '仓储'
    QUALITY = '质检'

    CHOICES = [
        (ADMIN, _('系统管理员')),
        (MANAGER, _('经理')),
        (SUPERVISOR, _('主管')),
        (OPERATOR, _('操作员')),
        (SALESPERSON, _('业务员')),
        (FINANCE, _('财务')),
        (WAREHOUSE, _('仓储')),
        (QUALITY, _('质检')),
    ]


class PermissionAction:
    """权限操作常量"""

    VIEW = 'view'
    ADD = 'add'
    CHANGE = 'change'
    DELETE = 'delete'
    EXPORT = 'export'
    APPROVE = 'approve'
    ASSIGN = 'assign'

    CHOICES = [
        (VIEW, _('查看')),
        (ADD, _('添加')),
        (CHANGE, _('修改')),
        (DELETE, _('删除')),
        (EXPORT, _('导出')),
        (APPROVE, _('审核')),
        (ASSIGN, _('分派')),
    ]


# 资源权限前缀常量
WORKORDER = 'workorder'
TASK = 'task'
PROCESS = 'process'
CUSTOMER = 'customer'
PRODUCT = 'product'
MATERIAL = 'material'
SUPPLIER = 'supplier'


# 权限组名称常量
class PermissionGroups:
    """权限组常量"""

    SYSTEM_ADMINS = '系统管理员'
    MANAGERS = '经理'
    SUPERVISORS = '主管'
    OPERATORS = '操作员'
    SALESPERSONS = '业务员'
    FINANCE = '财务'
    WAREHOUSE = '仓储'
    QUALITY = '质检'

    LEGACY_ALIASES = {
        'administrators': SYSTEM_ADMINS,
        'managers': MANAGERS,
        'supervisor': SUPERVISORS,
        'operators': OPERATORS,
        'salespersons': SALESPERSONS,
    }

    ALL = [
        SYSTEM_ADMINS,
        MANAGERS,
        SUPERVISORS,
        OPERATORS,
        SALESPERSONS,
        FINANCE,
        WAREHOUSE,
        QUALITY,
    ]
