"""施工单物料业务服务"""

from django.utils import timezone
from rest_framework import status

from workorder.constants.status import MaterialPurchaseStatus
from workorder.models.core import WorkOrderMaterial
from workorder.services.service_errors import ServiceError


class WorkOrderMaterialService:
    """施工单物料业务服务"""

    @staticmethod
    def confirm_cutting(
        *,
        wom: WorkOrderMaterial,
        user,
        cut_quantity=None,
        wastage_quantity=None,
        notes: str = "",
    ) -> WorkOrderMaterial:
        """确认物料开料完成。

        将物料状态从 'received' 转换为 'cut'，触发信号自动完成相关开料任务。
        """
        if wom.purchase_status != MaterialPurchaseStatus.RECEIVED:
            raise ServiceError(
                f"物料当前状态为 '{wom.get_purchase_status_display()}'，"
                f"只有 '已回料' 状态可以确认开料",
                code=status.HTTP_400_BAD_REQUEST,
            )

        wom.purchase_status = MaterialPurchaseStatus.CUT
        wom.cut_date = timezone.now().date()
        wom.cut_by = user
        update_fields = ["purchase_status", "cut_date", "cut_by"]

        if cut_quantity is not None:
            wom.cut_quantity = cut_quantity
            update_fields.append("cut_quantity")

        if wastage_quantity is not None:
            wom.wastage_quantity = wastage_quantity
            update_fields.append("wastage_quantity")

        log_parts = [f"确认开料 by {user.username}"]
        if cut_quantity is not None:
            log_parts.append(f"实际开料数量: {cut_quantity}")
        if wastage_quantity is not None:
            log_parts.append(f"损耗数量: {wastage_quantity}")
        if notes:
            log_parts.append(f"备注: {notes}")

        existing = wom.notes or ""
        log_line = " | ".join(log_parts)
        wom.notes = f"{existing}\n{log_line}" if existing else log_line
        update_fields.append("notes")

        wom.save(update_fields=update_fields)
        return wom
