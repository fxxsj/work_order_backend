"""
WorkOrderMaterial 视图集
"""

"""
核心业务视图集

包含施工单、工序、任务、产品、物料、日志等核心业务视图集。
"""

from decimal import Decimal

from django.db import models
from django.db.models import Avg, Count, F, Max, Q, Sum
from django.utils import timezone
from django_filters import CharFilter, FilterSet, NumberFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from workorder.response import APIResponse
from workorder.docs.work_orders_items import work_order_material_docs

from ..export_utils import export_tasks, export_work_orders
from ..models.assets import Artwork, Die
from ..models.base import Customer, Department, Process
from ..models.core import (
    ProcessLog,
    WorkOrder,
    WorkOrderMaterial,
    WorkOrderProcess,
    WorkOrderProduct,
    WorkOrderTask,
)
from ..models.materials import Material
from ..models.products import Product, ProductMaterial
from ..permissions import (
    SuperuserFriendlyModelPermissions,
    WorkOrderDataPermission,
    WorkOrderMaterialPermission,
    WorkOrderProcessPermission,
    WorkOrderTaskPermission,
)
from ..serializers.base import ProcessSerializer
from ..serializers.core import (
    ProcessLogSerializer,
    WorkOrderCreateUpdateSerializer,
    WorkOrderDetailSerializer,
    WorkOrderListSerializer,
    WorkOrderMaterialSerializer,
    WorkOrderProcessSerializer,
    WorkOrderProcessUpdateSerializer,
    WorkOrderProductSerializer,
    WorkOrderTaskSerializer,
)

# P1 优化: 导入自定义速率限制
from ..throttling import ApprovalRateThrottle, CreateRateThrottle, ExportRateThrottle


@work_order_material_docs
class WorkOrderMaterialViewSet(viewsets.ModelViewSet):
    """施工单物料视图集"""

    queryset = WorkOrderMaterial.objects.all()
    permission_classes = [
        WorkOrderMaterialPermission
    ]  # 使用自定义权限：如果有编辑施工单权限，就可以编辑其物料
    serializer_class = WorkOrderMaterialSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["work_order", "material", "purchase_status"]

    @action(detail=True, methods=["post"])
    def confirm_cutting(self, request, pk=None):
        """
        确认物料开料完成。

        POST /workorder-materials/{id}/confirm_cutting/

        将物料状态从 'received'(已回料) 转换为 'cut'(已开料)，
        触发信号自动完成相关开料任务。

        请求体（可选）：
        - cut_quantity: 实际开料数量
        - wastage_quantity: 开料损耗数量
        - notes: 备注
        """
        from workorder.constants.status import MaterialPurchaseStatus
        from workorder.services.service_errors import ServiceError

        wom = self.get_object()

        # 只允许已回料状态确认开料，防止 ordered/pending 直接跳过入库
        if wom.purchase_status != MaterialPurchaseStatus.RECEIVED:
            raise ServiceError(
                f"物料当前状态为 '{wom.get_purchase_status_display()}'，"
                f"只有 '已回料' 状态可以确认开料",
                code=status.HTTP_400_BAD_REQUEST,
            )

        notes = request.data.get("notes", "")
        cut_quantity = request.data.get("cut_quantity")
        wastage_quantity = request.data.get("wastage_quantity")

        wom.purchase_status = MaterialPurchaseStatus.CUT
        wom.cut_date = timezone.now().date()
        update_fields = ["purchase_status", "cut_date"]

        # 记录操作人、实际开料数量、损耗到备注
        log_parts = [f"确认开料 by {request.user.username}"]
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

        # post_save 信号会触发 update_cutting_tasks_on_material_cut()
        # 自动完成关联的开料任务

        serializer = self.get_serializer(wom)
        return APIResponse.success(
            data=serializer.data,
            message="物料开料确认成功，相关任务已更新",
        )
