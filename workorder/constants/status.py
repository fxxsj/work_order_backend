"""
统一的状态常量定义

此模块定义了系统中所有状态相关的常量，消除代码中的魔法字符串。
"""

from django.utils.translation import gettext_lazy as _


class WorkOrderStatus:
    """施工单状态常量"""

    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    CHOICES = [
        (PENDING, _('待开始')),
        (IN_PROGRESS, _('进行中')),
        (PAUSED, _('已暂停')),
        (COMPLETED, _('已完成')),
        (CANCELLED, _('已取消')),
    ]


class WorkOrderApprovalStatus:
    """施工单审核状态常量"""

    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

    CHOICES = [
        (PENDING, _('待审核')),
        (APPROVED, _('已通过')),
        (REJECTED, _('已拒绝')),
    ]


class TaskStatus:
    """任务状态常量"""

    DRAFT = 'draft'
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    CHOICES = [
        (DRAFT, _('草稿')),
        (PENDING, _('待开始')),
        (IN_PROGRESS, _('进行中')),
        (PAUSED, _('已暂停')),
        (COMPLETED, _('已完成')),
        (CANCELLED, _('已取消')),
    ]


class ProcessStatus:
    """工序状态常量"""

    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    CHOICES = [
        (PENDING, _('待开始')),
        (IN_PROGRESS, _('进行中')),
        (PAUSED, _('已暂停')),
        (COMPLETED, _('已完成')),
        (CANCELLED, _('已取消')),
    ]


class MaterialPurchaseStatus:
    """物料采购状态常量"""

    PENDING = 'pending'
    ORDERED = 'ordered'
    RECEIVED = 'received'
    CUT = 'cut'
    COMPLETED = 'completed'

    CHOICES = [
        (PENDING, _('待采购')),
        (ORDERED, _('已订购')),
        (RECEIVED, _('已收货')),
        (CUT, _('已开料')),
        (COMPLETED, _('已完成')),
    ]


class ApprovalStepStatus:
    """审核步骤状态常量"""

    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    SKIPPED = 'skipped'

    CHOICES = [
        (PENDING, _('待执行')),
        (IN_PROGRESS, _('执行中')),
        (COMPLETED, _('已完成')),
        (SKIPPED, _('已跳过')),
    ]


class ApprovalEscalationStatus:
    """审核上报状态常量"""

    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    RESOLVED = 'resolved'

    CHOICES = [
        (PENDING, _('待处理')),
        (ACCEPTED, _('已接受')),
        (REJECTED, _('已拒绝')),
        (RESOLVED, _('已处理')),
    ]


class NotificationStatus:
    """通知状态常量"""

    PENDING = 'pending'
    SENT = 'sent'
    READ = 'read'
    FAILED = 'failed'

    CHOICES = [
        (PENDING, _('待发送')),
        (SENT, _('已发送')),
        (READ, _('已读取')),
        (FAILED, _('发送失败')),
    ]


class DeliveryOrderStatus:
    """发货单状态常量"""

    PENDING = 'pending'
    PREPARING = 'preparing'
    SHIPPED = 'shipped'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'

    CHOICES = [
        (PENDING, _('待发货')),
        (PREPARING, _('准备中')),
        (SHIPPED, _('已发货')),
        (DELIVERED, _('已送达')),
        (CANCELLED, _('已取消')),
    ]


class QualityInspectionStatus:
    """质检状态常量"""

    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    PASSED = 'passed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

    CHOICES = [
        (PENDING, _('待质检')),
        (IN_PROGRESS, _('质检中')),
        (PASSED, _('合格')),
        (FAILED, _('不合格')),
        (CANCELLED, _('已取消')),
    ]


class StockTransactionStatus:
    """库存交易状态常量"""

    PENDING = 'pending'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    CHOICES = [
        (PENDING, _('待处理')),
        (COMPLETED, _('已完成')),
        (CANCELLED, _('已取消')),
    ]
