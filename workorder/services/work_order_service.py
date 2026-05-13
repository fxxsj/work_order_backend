"""
施工单相关服务

将 WorkOrderViewSet 中的业务逻辑下沉到服务层，保持 views 仅负责入参/出参。
"""

from __future__ import annotations

import logging

from django.db.models import Max
from django.utils import timezone
from rest_framework import status

from workorder.constants.status import WorkOrderApprovalStatus, WorkOrderStatus
from ..permissions.permission_utils import is_sales_user
from ..models.base import Process
from ..models.core import WorkOrder, WorkOrderMaterial, WorkOrderProcess
from ..models.materials import Material
from ..models.system import Notification, WorkOrderApprovalLog
from .service_errors import ServiceError

logger = logging.getLogger(__name__)


class WorkOrderService:
    @staticmethod
    def add_process(
        *, work_order: WorkOrder, process_id, sequence=0
    ) -> WorkOrderProcess:
        if not process_id:
            raise ServiceError(
                "请提供工序ID",
                code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            process = Process.objects.get(id=process_id)
        except Process.DoesNotExist as exc:
            raise ServiceError(
                "工序不存在",
                code=status.HTTP_404_NOT_FOUND,
            ) from exc

        existing_process = WorkOrderProcess.objects.filter(
            work_order=work_order, sequence=sequence
        ).first()
        if existing_process:
            max_sequence = (
                WorkOrderProcess.objects.filter(work_order=work_order).aggregate(
                    Max("sequence")
                )["sequence__max"]
                or 0
            )
            sequence = max_sequence + 1

        existing_same_process = WorkOrderProcess.objects.filter(
            work_order=work_order, process=process
        ).first()
        if existing_same_process:
            raise ServiceError(
                "该工序已经添加到施工单中",
                code=status.HTTP_400_BAD_REQUEST,
            )

        return WorkOrderProcess.objects.create(
            work_order=work_order, process=process, sequence=sequence
        )

    @staticmethod
    def add_material(
        *, work_order: WorkOrder, material_id, notes: str = ""
    ) -> WorkOrderMaterial:
        if not material_id:
            raise ServiceError(
                "请提供物料ID",
                code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            material = Material.objects.get(id=material_id)
        except Material.DoesNotExist as exc:
            raise ServiceError(
                "物料不存在",
                code=status.HTTP_404_NOT_FOUND,
            ) from exc

        return WorkOrderMaterial.objects.create(
            work_order=work_order, material=material, notes=notes
        )

    @staticmethod
    def update_status(*, work_order: WorkOrder, new_status: str) -> WorkOrder:
        if new_status not in dict(WorkOrder.STATUS_CHOICES):
            raise ServiceError(
                "无效的状态",
                code=status.HTTP_400_BAD_REQUEST,
            )

        work_order.status = new_status
        work_order.save()
        return work_order

    @staticmethod
    def approve(
        *,
        work_order: WorkOrder,
        user,
        approval_status: str,
        approval_comment: str = "",
        rejection_reason: str = "",
    ) -> WorkOrder:
        if approval_status not in ["approved", "rejected"]:
            raise ServiceError(
                "审核状态无效，必须是 approved 或 rejected",
                code=status.HTTP_400_BAD_REQUEST,
            )

        if not is_sales_user(user):
            raise ServiceError(
                "只有业务员可以审核施工单",
                code=status.HTTP_403_FORBIDDEN,
            )

        if work_order.customer.salesperson != user:
            raise ServiceError(
                "只能审核自己负责的施工单",
                code=status.HTTP_403_FORBIDDEN,
            )

        if work_order.approval_status != "submitted":
            message = (
                '只有待审核的施工单可以审核。如需重新审核，请先使用"请求重新审核"功能。'
            )
            raise ServiceError(
                message,
                code=status.HTTP_400_BAD_REQUEST,
            )

        if approval_status == "rejected" and not rejection_reason:
            raise ServiceError(
                "审核拒绝时，必须填写拒绝原因",
                code=status.HTTP_400_BAD_REQUEST,
            )

        validation_errors = work_order.validate_before_approval()
        if validation_errors:
            raise ServiceError(
                "施工单数据不完整，无法审核",
                code=status.HTTP_400_BAD_REQUEST,
                data={"details": validation_errors},
            )

        WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            approval_status=approval_status,
            approved_by=user,
            approval_comment=approval_comment,
            rejection_reason=rejection_reason,
        )

        work_order.approval_status = approval_status
        work_order.approved_by = user
        work_order.approved_at = timezone.now()
        work_order.approval_comment = approval_comment

        if approval_status == WorkOrderApprovalStatus.APPROVED and work_order.status == WorkOrderStatus.PENDING:
            work_order.status = WorkOrderStatus.IN_PROGRESS

        work_order.save()

        if approval_status == WorkOrderApprovalStatus.APPROVED:
            Notification.create_notification(
                recipient=work_order.created_by,
                notification_type="approval_passed",
                title="施工单已审核通过",
                content=f"施工单 {work_order.order_number} 已审核通过",
                priority="high",
                work_order=work_order,
                template_key="approval_passed",
                template_variables={
                    "workorder_number": work_order.order_number,
                    "approved_by": user.username if user else "系统",
                },
            )
        else:
            Notification.create_notification(
                recipient=work_order.created_by,
                notification_type="approval_rejected",
                title="施工单审核被拒绝",
                content=f"施工单 {work_order.order_number} 审核被拒绝",
                priority="high",
                work_order=work_order,
                template_key="approval_rejected",
                template_variables={
                    "workorder_number": work_order.order_number,
                    "reason": rejection_reason or "",
                    "approved_by": user.username if user else "系统",
                },
            )

        return work_order

    @staticmethod
    def resubmit_for_approval(*, work_order: WorkOrder, user) -> WorkOrder:
        if work_order.approval_status != WorkOrderApprovalStatus.REJECTED:
            raise ServiceError(
                "只有被拒绝的施工单才能重新提交审核",
                code=status.HTTP_400_BAD_REQUEST,
            )

        if work_order.manager != user and work_order.created_by != user:
            if not user.has_perm("workorder.change_workorder"):
                raise ServiceError(
                    "只有制表人、创建人或有编辑权限的用户才能重新提交审核",
                    code=status.HTTP_403_FORBIDDEN,
                )

        work_order.approval_status = WorkOrderApprovalStatus.SUBMITTED
        work_order.approval_comment = ""
        work_order.save()
        return work_order
