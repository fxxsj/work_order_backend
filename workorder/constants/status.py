"""
统一的状态常量定义

此模块定义了系统中所有状态相关的常量，消除代码中的魔法字符串。
"""

from django.utils.translation import gettext_lazy as _


class WorkOrderStatus:
    """施工单状态常量"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    CHOICES = [
        (PENDING, _("待开始")),
        (IN_PROGRESS, _("进行中")),
        (PAUSED, _("已暂停")),
        (COMPLETED, _("已完成")),
        (CANCELLED, _("已取消")),
    ]


class WorkOrderApprovalStatus:
    """施工单审核状态常量

    与 ApprovalFieldsMixin.choices 对齐：draft / submitted / approved / rejected
    注意：不再包含 PENDING，提交审核后统一使用 SUBMITTED。
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"

    CHOICES = [
        (DRAFT, _("草稿")),
        (SUBMITTED, _("待审核")),
        (APPROVED, _("已通过")),
        (REJECTED, _("已拒绝")),
    ]


class TaskStatus:
    """任务状态常量"""

    DRAFT = "draft"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    CHOICES = [
        (DRAFT, _("草稿")),
        (PENDING, _("待开始")),
        (IN_PROGRESS, _("进行中")),
        (PAUSED, _("已暂停")),
        (COMPLETED, _("已完成")),
        (CANCELLED, _("已取消")),
    ]


class ProcessStatus:
    """工序状态常量"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    CHOICES = [
        (PENDING, _("待开始")),
        (IN_PROGRESS, _("进行中")),
        (PAUSED, _("已暂停")),
        (COMPLETED, _("已完成")),
        (CANCELLED, _("已取消")),
    ]


class MaterialPurchaseStatus:
    """物料采购状态常量"""

    PENDING = "pending"
    ORDERED = "ordered"
    RECEIVED = "received"
    CUT = "cut"
    COMPLETED = "completed"

    CHOICES = [
        (PENDING, _("待采购")),
        (ORDERED, _("已订购")),
        (RECEIVED, _("已收货")),
        (CUT, _("已开料")),
        (COMPLETED, _("已完成")),
    ]


class NotificationStatus:
    """通知状态常量"""

    PENDING = "pending"
    SENT = "sent"
    READ = "read"
    FAILED = "failed"

    CHOICES = [
        (PENDING, _("待发送")),
        (SENT, _("已发送")),
        (READ, _("已读取")),
        (FAILED, _("发送失败")),
    ]


class DeliveryOrderStatus:
    """送货单状态常量"""

    PENDING = "pending"
    PREPARING = "preparing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

    CHOICES = [
        (PENDING, _("待发货")),
        (PREPARING, _("准备中")),
        (SHIPPED, _("已发货")),
        (DELIVERED, _("已送达")),
        (CANCELLED, _("已取消")),
    ]


class QualityInspectionStatus:
    """质检状态常量"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    CHOICES = [
        (PENDING, _("待质检")),
        (IN_PROGRESS, _("质检中")),
        (PASSED, _("合格")),
        (FAILED, _("不合格")),
        (CANCELLED, _("已取消")),
    ]


class StockTransactionStatus:
    """库存交易状态常量"""

    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    CHOICES = [
        (PENDING, _("待处理")),
        (COMPLETED, _("已完成")),
        (CANCELLED, _("已取消")),
    ]


class SalesOrderStatus:
    """客户订单状态常量"""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PRODUCTION = "in_production"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    CHOICES = [
        (DRAFT, _("草稿")),
        (SUBMITTED, _("已提交")),
        (APPROVED, _("已审核")),
        (REJECTED, _("已拒绝")),
        (IN_PRODUCTION, _("生产中")),
        (COMPLETED, _("已完成")),
        (CANCELLED, _("已取消")),
    ]


class TaskType:
    """任务类型常量"""

    PLATE_MAKING = "plate_making"
    CUTTING = "cutting"
    PRINTING = "printing"
    PACKAGING = "packaging"
    QUALITY_CHECK = "quality_check"
    FOILING = "foiling"
    EMBOSSING = "embossing"
    DIE_CUTTING = "die_cutting"
    GENERAL = "general"

    CHOICES = [
        (PLATE_MAKING, _("制版")),
        (CUTTING, _("开料")),
        (PRINTING, _("印刷")),
        (PACKAGING, _("包装")),
        (QUALITY_CHECK, _("质检")),
        (FOILING, _("烫金")),
        (EMBOSSING, _("压凸")),
        (DIE_CUTTING, _("模切")),
        (GENERAL, _("通用")),
    ]


class InvoiceStatus:
    """发票状态常量"""

    DRAFT = "draft"
    ISSUED = "issued"
    SENT = "sent"
    RECEIVED = "received"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

    CHOICES = [
        (DRAFT, _("待开具")),
        (ISSUED, _("已开具")),
        (SENT, _("已发送")),
        (RECEIVED, _("已收到")),
        (CANCELLED, _("已作废")),
        (REFUNDED, _("已红冲")),
    ]


class PaymentPlanStatus:
    """收款计划状态常量"""

    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETED = "completed"

    CHOICES = [
        (PENDING, _("待收款")),
        (PARTIAL, _("部分收款")),
        (COMPLETED, _("已完成")),
    ]


class StockInStatus:
    """入库单状态常量"""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    CHOICES = [
        (DRAFT, _("草稿")),
        (SUBMITTED, _("已提交")),
        (APPROVED, _("已审核")),
        (COMPLETED, _("已完成")),
        (CANCELLED, _("已取消")),
    ]


class StockOutStatus:
    """出库单状态常量"""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    CHOICES = [
        (DRAFT, _("草稿")),
        (SUBMITTED, _("已提交")),
        (APPROVED, _("已审核")),
        (COMPLETED, _("已完成")),
        (CANCELLED, _("已取消")),
    ]


class DeliveryOrderModelStatus:
    """送货单状态常量（模型层，与 DeliveryOrderStatus 含义不同）"""

    PENDING = "pending"
    SHIPPED = "shipped"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    REJECTED = "rejected"
    RETURNED = "returned"

    CHOICES = [
        (PENDING, _("待发货")),
        (SHIPPED, _("已发货")),
        (IN_TRANSIT, _("运输中")),
        (RECEIVED, _("已签收")),
        (REJECTED, _("拒收")),
        (RETURNED, _("已退货")),
    ]


class StatementStatus:
    """对账单状态常量"""

    DRAFT = "draft"
    SENT = "sent"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"

    CHOICES = [
        (DRAFT, _("草稿")),
        (SENT, _("已发送")),
        (CONFIRMED, _("已确认")),
        (DISPUTED, _("有异议")),
    ]
