"""
流程通知触发器（补充模块）

为 WorkOrderFlowService 提供的通知触发方法
与 notification_triggers.py 配合使用
"""

import logging
from typing import Dict, Any, Optional
from django.contrib.auth.models import User

from ..models.core import WorkOrder, WorkOrderTask
from ..models.system import Notification
from .realtime_notification import (
    notification_service,
    NotificationEvent,
    NotificationPriority,
)

logger = logging.getLogger(__name__)


class NotificationTriggers:
    """
    流程通知触发器

    封装所有流程相关的通知逻辑
    """

    @staticmethod
    def notify_workorder_created(
        work_order: WorkOrder, recipient: User
    ) -> None:
        """
        通知施工单已创建

        Args:
            work_order: 施工单对象
            recipient: 通知接收人
        """
        Notification.create_notification(
            recipient=recipient,
            notification_type="workorder_created",
            title=f"施工单 {work_order.order_number} 已创建",
            content=f"施工单 {work_order.order_number} 已成功创建，客户：{work_order.customer.name}，"
            f"金额：¥{work_order.total_amount:.2f}",
            priority="normal",
            work_order=work_order,
        )

        # 实时推送
        notification_service.send_notification(
            event_type=NotificationEvent.WORKORDER_CREATED,
            recipients=[recipient],
            data={
                "title": "施工单已创建",
                "message": f"施工单 {work_order.order_number} 已创建",
                "workorder_id": work_order.id,
                "workorder_number": work_order.order_number,
                "customer": work_order.customer.name,
                "total_amount": float(work_order.total_amount),
                "priority": work_order.priority,
            },
            priority=NotificationPriority.NORMAL,
        )

        logger.info(f"已通知 {recipient.username}：施工单 {work_order.order_number} 已创建")

    @staticmethod
    def notify_approval_requested(
        work_order: WorkOrder,
        recipient: User,
        comment: str = "",
    ) -> None:
        """
        通知业务员：有施工单待审核

        Args:
            work_order: 施工单对象
            recipient: 业务员（审核人）
            comment: 提交备注
        """
        content = f"施工单 {work_order.order_number} 待审核，客户：{work_order.customer.name}，"
        content += f"金额：¥{work_order.total_amount:.2f}"
        if comment:
            content += f"\n提交备注：{comment}"

        Notification.create_notification(
            recipient=recipient,
            notification_type="approval_requested",
            title=f"待审核：施工单 {work_order.order_number}",
            content=content,
            priority="high",
            work_order=work_order,
        )

        # 实时推送
        notification_service.send_notification(
            event_type=NotificationEvent.APPROVAL_REQUESTED,
            recipients=[recipient],
            data={
                "title": "施工单待审核",
                "message": f"施工单 {work_order.order_number} 待审核",
                "workorder_id": work_order.id,
                "workorder_number": work_order.order_number,
                "customer": work_order.customer.name,
                "total_amount": float(work_order.total_amount),
                "priority": work_order.priority,
            },
            priority=NotificationPriority.HIGH,
        )

        logger.info(f"已通知业务员 {recipient.username}：施工单 {work_order.order_number} 待审核")

    @staticmethod
    def notify_approval_passed(
        work_order: WorkOrder,
        dispatch_result: Dict[str, Any],
    ) -> None:
        """
        通知相关人员：施工单已审核通过

        Args:
            work_order: 施工单对象
            dispatch_result: 任务分派结果
        """
        # 1. 通知创建人
        Notification.create_notification(
            recipient=work_order.created_by,
            notification_type="approval_passed",
            title=f"施工单 {work_order.order_number} 已审核通过",
            content=f"施工单 {work_order.order_number} 已通过审核，"
            f"已自动分派 {dispatch_result['dispatched_count']} 个任务。",
            priority="high",
            work_order=work_order,
        )

        # 2. 通知所有被分派任务的操作员
        for operator_id in dispatch_result.get("notified_operators", []):
            try:
                operator = User.objects.get(id=operator_id)
                Notification.create_notification(
                    recipient=operator,
                    notification_type="task_assigned",
                    title=f"新任务分派：施工单 {work_order.order_number}",
                    content=f"您有 {dispatch_result['operator_tasks'].get(operator_id, 0)} 个新任务，"
                    f"来自施工单 {work_order.order_number}，请及时处理。",
                    priority="high",
                    work_order=work_order,
                )
            except User.DoesNotExist:
                logger.warning(f"用户 ID {operator_id} 不存在，跳过通知")

        # 3. 实时推送
        notification_service.send_notification(
            event_type=NotificationEvent.APPROVAL_PASSED,
            recipients=[work_order.created_by],
            data={
                "title": "施工单已审核通过",
                "message": f"施工单 {work_order.order_number} 已审核通过",
                "workorder_id": work_order.id,
                "workorder_number": work_order.order_number,
                "dispatched_count": dispatch_result["dispatched_count"],
            },
            priority=NotificationPriority.HIGH,
        )

        logger.info(f"已通知相关人员：施工单 {work_order.order_number} 已审核通过")

    @staticmethod
    def notify_approval_rejected(
        work_order: WorkOrder,
        recipient: User,
        reason: str,
    ) -> None:
        """
        通知创建人：施工单审核被拒绝

        Args:
            work_order: 施工单对象
            recipient: 创建人
            reason: 拒绝原因
        """
        Notification.create_notification(
            recipient=recipient,
            notification_type="approval_rejected",
            title=f"施工单 {work_order.order_number} 审核被拒绝",
            content=f"施工单 {work_order.order_number} 审核被拒绝。\n"
            f"拒绝原因：{reason}",
            priority="high",
            work_order=work_order,
        )

        # 实时推送
        notification_service.send_notification(
            event_type=NotificationEvent.APPROVAL_REJECTED,
            recipients=[recipient],
            data={
                "title": "施工单审核被拒绝",
                "message": f"施工单 {work_order.order_number} 审核被拒绝",
                "workorder_id": work_order.id,
                "workorder_number": work_order.order_number,
                "reason": reason,
            },
            priority=NotificationPriority.HIGH,
        )

        logger.info(f"已通知 {recipient.username}：施工单 {work_order.order_number} 审核被拒绝")

    @staticmethod
    def notify_workorder_completed(work_order: WorkOrder) -> None:
        """
        通知相关人员：施工单已完成

        Args:
            work_order: 施工单对象
        """
        # 通知创建人
        Notification.create_notification(
            recipient=work_order.created_by,
            notification_type="workorder_completed",
            title=f"施工单 {work_order.order_number} 已完成",
            content=f"施工单 {work_order.order_number} 的所有任务已完成，施工单状态已变更为「已完成」。",
            priority="normal",
            work_order=work_order,
        )

        # 实时推送
        notification_service.send_notification(
            event_type=NotificationEvent.WORKORDER_COMPLETED,
            recipients=[work_order.created_by],
            data={
                "title": "施工单已完成",
                "message": f"施工单 {work_order.order_number} 已完成",
                "workorder_id": work_order.id,
                "workorder_number": work_order.order_number,
                "customer": work_order.customer.name,
            },
            priority=NotificationPriority.NORMAL,
        )

        logger.info(f"已通知 {work_order.created_by.username}：施工单 {work_order.order_number} 已完成")
