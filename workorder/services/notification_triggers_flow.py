"""
流程通知触发器（补充模块）

为 WorkOrderFlowService 提供的通知触发方法
与 notification_triggers.py 配合使用
"""

import logging
from typing import Dict, Any
from django.contrib.auth.models import User

from ..models.core import WorkOrder
from ..models.system import Notification
from .realtime_notification import (
    notification_service,
    NotificationEvent,
    NotificationPriority,
)

logger = logging.getLogger(__name__)


class NotificationTriggers:
    """封装所有流程相关的通知逻辑。"""

    @staticmethod
    def _create_notification(
        *,
        recipient: User,
        notification_type: str,
        title: str,
        content: str,
        priority: str,
        work_order: WorkOrder,
        template_key: str,
        template_variables: dict,
    ) -> None:
        Notification.create_notification(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            content=content,
            priority=priority,
            work_order=work_order,
            template_key=template_key,
            template_variables=template_variables,
        )

    @staticmethod
    def _emit(
        *,
        recipients: list[User],
        notification_type: str,
        title: str,
        content: str,
        priority: str,
        template_key: str,
        event_type,
        work_order: WorkOrder,
        template_variables: dict,
        realtime_data: dict,
        realtime_priority,
    ) -> None:
        for recipient in recipients:
            NotificationTriggers._create_notification(
                recipient=recipient,
                notification_type=notification_type,
                title=title,
                content=content,
                priority=priority,
                work_order=work_order,
                template_key=template_key,
                template_variables=template_variables,
            )

        notification_service.send_notification(
            event_type=event_type,
            recipients=recipients,
            data=realtime_data,
            priority=realtime_priority,
        )

    @staticmethod
    def notify_workorder_created(
        work_order: WorkOrder, recipient: User
    ) -> None:
        NotificationTriggers._emit(
            recipients=[recipient],
            notification_type="workorder_created",
            title="施工单已创建",
            content=f"施工单 {work_order.order_number} 已成功创建",
            priority="normal",
            template_key="workorder_created",
            event_type=NotificationEvent.WORKORDER_CREATED,
            work_order=work_order,
            template_variables={
                "workorder_number": work_order.order_number,
                "customer": (
                    work_order.customer.name if work_order.customer else ""
                ),
                "total_amount": f"{work_order.total_amount:.2f}",
            },
            realtime_data={
                "workorder_id": work_order.id,
                "workorder_number": work_order.order_number,
                "customer": (
                    work_order.customer.name if work_order.customer else ""
                ),
                "total_amount": float(work_order.total_amount),
                "priority": work_order.priority,
            },
            realtime_priority=NotificationPriority.NORMAL,
        )

        logger.info(
            f"已通知 {recipient.username}：施工单 {work_order.order_number} 已创建"
        )

    @staticmethod
    def notify_approval_requested(
        work_order: WorkOrder,
        recipient: User,
        comment: str = "",
    ) -> None:
        content = (
            f"施工单 {work_order.order_number} 待审核，"
            f"客户：{work_order.customer.name}，"
        )
        content += f"金额：¥{work_order.total_amount:.2f}"
        if comment:
            content += f"\n提交备注：{comment}"

        NotificationTriggers._emit(
            recipients=[recipient],
            notification_type="approval_requested",
            title="施工单待审核",
            content=content,
            priority="high",
            template_key="approval_requested",
            event_type=NotificationEvent.APPROVAL_REQUESTED,
            work_order=work_order,
            template_variables={
                "workorder_number": work_order.order_number,
                "customer": (
                    work_order.customer.name if work_order.customer else ""
                ),
                "total_amount": f"{work_order.total_amount:.2f}",
                "comment": comment,
            },
            realtime_data={
                "workorder_id": work_order.id,
                "workorder_number": work_order.order_number,
                "customer": (
                    work_order.customer.name if work_order.customer else ""
                ),
                "total_amount": float(work_order.total_amount),
                "priority": work_order.priority,
                "comment": comment,
            },
            realtime_priority=NotificationPriority.HIGH,
        )

        logger.info(
            f"已通知业务员 {recipient.username}：施工单 {work_order.order_number} 待审核"
        )

    @staticmethod
    def notify_approval_passed(
        work_order: WorkOrder,
        dispatch_result: Dict[str, Any],
    ) -> None:
        # 1. 通知创建人
        NotificationTriggers._emit(
            recipients=[work_order.created_by],
            notification_type="approval_passed",
            title="施工单已审核通过",
            content=f"施工单 {work_order.order_number} 已审核通过",
            priority="high",
            template_key="approval_passed",
            event_type=NotificationEvent.APPROVAL_PASSED,
            work_order=work_order,
            template_variables={
                "workorder_number": work_order.order_number,
                "dispatched_count": dispatch_result["dispatched_count"],
            },
            realtime_data={
                "workorder_id": work_order.id,
                "workorder_number": work_order.order_number,
                "dispatched_count": dispatch_result["dispatched_count"],
            },
            realtime_priority=NotificationPriority.HIGH,
        )

        # 2. 通知所有被分派任务的操作员
        for operator_id in dispatch_result.get("notified_operators", []):
            try:
                operator = User.objects.get(id=operator_id)
                operator_task_count = dispatch_result[
                    "operator_tasks"
                ].get(operator_id, 0)
                NotificationTriggers._create_notification(
                    recipient=operator,
                    notification_type="task_assigned",
                    title="新任务分配",
                    content=f"您有新的任务，来自施工单 {work_order.order_number}",
                    priority="high",
                    work_order=work_order,
                    template_key="task_assigned",
                    template_variables={
                        "task_name": (
                            f"{operator_task_count} 个新任务"
                        ),
                        "workorder_number": work_order.order_number,
                        "assigned_by": "系统",
                    },
                )
            except User.DoesNotExist:
                logger.warning(f"用户 ID {operator_id} 不存在，跳过通知")

        logger.info(
            f"已通知相关人员：施工单 {work_order.order_number} 已审核通过"
        )

    @staticmethod
    def notify_approval_rejected(
        work_order: WorkOrder,
        recipient: User,
        reason: str,
    ) -> None:
        NotificationTriggers._emit(
            recipients=[recipient],
            notification_type="approval_rejected",
            title="施工单审核被拒绝",
            content=f"施工单 {work_order.order_number} 审核被拒绝",
            priority="high",
            template_key="approval_rejected",
            event_type=NotificationEvent.APPROVAL_REJECTED,
            work_order=work_order,
            template_variables={
                "workorder_number": work_order.order_number,
                "reason": reason,
            },
            realtime_data={
                "workorder_id": work_order.id,
                "workorder_number": work_order.order_number,
                "reason": reason,
            },
            realtime_priority=NotificationPriority.HIGH,
        )

        logger.info(
            f"已通知 {recipient.username}：施工单 {work_order.order_number} 审核被拒绝"
        )

    @staticmethod
    def notify_workorder_completed(work_order: WorkOrder) -> None:
        # 通知创建人
        NotificationTriggers._emit(
            recipients=[work_order.created_by],
            notification_type="workorder_completed",
            title="施工单已完成",
            content=f"施工单 {work_order.order_number} 已完成",
            priority="normal",
            template_key="workorder_completed",
            event_type=NotificationEvent.WORKORDER_COMPLETED,
            work_order=work_order,
            template_variables={
                "workorder_number": work_order.order_number,
                "customer": (
                    work_order.customer.name if work_order.customer else ""
                ),
            },
            realtime_data={
                "workorder_id": work_order.id,
                "workorder_number": work_order.order_number,
                "customer": (
                    work_order.customer.name if work_order.customer else ""
                ),
            },
            realtime_priority=NotificationPriority.NORMAL,
        )

        logger.info(
            f"已通知 {work_order.created_by.username}："
            f"施工单 {work_order.order_number} 已完成"
        )
