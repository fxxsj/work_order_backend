"""
审核相关常量定义

此模块定义了多级审核系统中的常量。
"""

from django.utils.translation import gettext_lazy as _


class WorkflowType:
    """审核工作流类型常量"""

    SIMPLE = 'simple'
    STANDARD = 'standard'
    COMPLEX = 'complex'
    URGENT = 'urgent'

    CHOICES = [
        (SIMPLE, _('简单订单')),
        (STANDARD, _('标准订单')),
        (COMPLEX, _('复杂订单')),
        (URGENT, _('紧急订单')),
    ]


class StepType:
    """审核步骤类型常量"""

    REVIEW = 'review'
    APPROVE = 'approve'
    REJECT = 'reject'
    ESCALATE = 'escalate'

    CHOICES = [
        (REVIEW, _('审核')),
        (APPROVE, _('批准')),
        (REJECT, _('拒绝')),
        (ESCALATE, _('上报')),
    ]


class DecisionType:
    """审核决定类型常量"""

    APPROVE = 'approve'
    REJECT = 'reject'
    ESCALATE = 'escalate'

    CHOICES = [
        (APPROVE, _('批准')),
        (REJECT, _('拒绝')),
        (ESCALATE, _('上报')),
    ]


class RuleType:
    """审核规则类型常量"""

    AMOUNT_THRESHOLD = 'amount_threshold'
    PRIORITY_MATCH = 'priority_match'
    CUSTOMER_TYPE = 'customer_type'
    PRODUCT_CATEGORY = 'product_category'
    CUSTOM_RULE = 'custom_rule'

    CHOICES = [
        (AMOUNT_THRESHOLD, _('金额阈值')),
        (PRIORITY_MATCH, _('优先级匹配')),
        (CUSTOMER_TYPE, _('客户类型')),
        (PRODUCT_CATEGORY, _('产品类别')),
        (CUSTOM_RULE, _('自定义规则')),
    ]
