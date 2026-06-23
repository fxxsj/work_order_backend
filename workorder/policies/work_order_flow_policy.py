"""施工单流程权限策略

集中 WorkOrderFlowViewSet 的权限校验逻辑，保持视图层只负责入参/出参。
"""

from django.contrib.auth.models import User
from rest_framework import status

from ..models.core import WorkOrder
from ..models.sales import SalesOrder
from ..permission_utils import PermissionUtils
from ..services.service_errors import ServiceError


class WorkOrderFlowPolicy:
    """施工单流程权限策略"""

    @staticmethod
    def require_permission(
        user: User, permission: str, message: str = "权限不足"
    ) -> None:
        if user.is_superuser or user.has_perm(permission):
            return
        raise ServiceError(message=message, code=status.HTTP_403_FORBIDDEN)

    @staticmethod
    def ensure_sales_order_visible(*, sales_order_id, user: User) -> None:
        if not sales_order_id:
            raise ServiceError(
                "请提供客户订单ID", code=status.HTTP_400_BAD_REQUEST
            )

        queryset = SalesOrder.objects.filter(id=sales_order_id)
        if user.is_superuser or PermissionUtils.is_finance_user(user):
            visible = queryset.exists()
        else:
            visible = queryset.filter(
                PermissionUtils.build_sales_order_scope_q(user, "")
            ).exists()

        if not visible:
            raise ServiceError(
                "客户订单不存在或无权访问", code=status.HTTP_404_NOT_FOUND
            )

    @staticmethod
    def ensure_work_order_writable(
        *, work_order: WorkOrder, user: User
    ) -> None:
        if user.is_superuser or user.has_perm("workorder.submit_workorder"):
            return
        raise ServiceError(
            "您没有提交审核的权限", code=status.HTTP_403_FORBIDDEN
        )

    @staticmethod
    def validate_approval_permissions(
        *, work_order: WorkOrder, user: User
    ) -> None:
        if work_order.approval_status != "submitted":
            raise ServiceError(
                '只有待审核的施工单可以审核。如需重新审核，请先使用"请求重新审核"功能。',
                code=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_superuser and not user.has_perm(
            "workorder.approve_workorder"
        ):
            raise ServiceError(
                "您没有审核施工单的权限",
                code=status.HTTP_403_FORBIDDEN,
            )
