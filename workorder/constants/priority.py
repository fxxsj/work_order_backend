"""
优先级常量定义

此模块定义了系统中所有优先级相关的常量。
"""

from django.utils.translation import gettext_lazy as _


class Priority:
    """通用优先级常量"""

    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    URGENT = 'urgent'

    CHOICES = [
        (LOW, _('低')),
        (NORMAL, _('普通')),
        (HIGH, _('高')),
        (URGENT, _('紧急')),
    ]


class WorkflowPriority:
    """工作流优先级常量（用于智能分派）"""

    HIGHEST = 100
    HIGH = 90
    ABOVE_NORMAL = 75
    NORMAL = 50
    BELOW_NORMAL = 25
    LOW = 15
    LOWEST = 5

    CHOICES = [
        (HIGHEST, _('最高')),
        (HIGH, _('高')),
        (ABOVE_NORMAL, _('高于正常')),
        (NORMAL, _('正常')),
        (BELOW_NORMAL, _('低于正常')),
        (LOW, _('低')),
        (LOWEST, _('最低')),
    ]
