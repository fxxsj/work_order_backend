"""
WorkOrderProcess 视图集
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
from rest_framework import status
from rest_framework.decorators import action
from workorder.response import APIResponse

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
from ..services.service_errors import ServiceError
from ..services.work_order_process_service import WorkOrderProcessService
from .base_viewsets import BaseViewSet


class WorkOrderProcessViewSet(BaseViewSet):
    """施工单工序视图集"""

    queryset = WorkOrderProcess.objects.select_related(
        "process", "department", "operator", "work_order"
    )
    permission_classes = [
        WorkOrderProcessPermission
    ]  # 使用自定义权限：如果有编辑施工单权限，就可以编辑其工序
    serializer_class = WorkOrderProcessSerializer
    filterset_fields = ["work_order", "process", "status", "operator", "department"]
    search_fields = ["work_order__order_number", "process__name", "department__name"]
    ordering_fields = ["sequence", "actual_start_time", "created_at"]
    ordering = ["work_order", "sequence"]

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return WorkOrderProcessUpdateSerializer
        return WorkOrderProcessSerializer

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """开始工序（生成任务）"""
        process = self.get_object()
        try:
            process = WorkOrderProcessService.start_process(
                process=process,
                user=request.user,
                operator_id=request.data.get("operator"),
                department_id=request.data.get("department"),
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        serializer = self.get_serializer(process)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """完成工序

        完成逻辑：
        1. 优先检查是否所有任务已完成，如果是则自动完成（推荐方式）
        2. 如果任务未完成，需要提供强制完成原因（force_complete=True）
        3. 强制完成时会同步更新所有任务状态为已完成
        """
        process = self.get_object()

        # 获取完成数量和不良品数量
        quantity_completed = request.data.get("quantity_completed", 0)
        quantity_defective = request.data.get("quantity_defective", 0)
        force_complete = request.data.get("force_complete", False)
        force_reason = request.data.get("force_reason", "")
        try:
            process = WorkOrderProcessService.complete_process(
                process=process,
                user=request.user,
                quantity_completed=quantity_completed,
                quantity_defective=quantity_defective,
                force_complete=force_complete,
                force_reason=force_reason,
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        serializer = self.get_serializer(process)
        return APIResponse.success(data=serializer.data)

    @action(detail=False, methods=["post"])
    def batch_start(self, request):
        """批量开始工序

        请求参数：
        - process_ids: 工序ID列表（必填）
        - operator: 操作员ID（可选，应用到所有工序）
        - department: 部门ID（可选，应用到所有工序）
        """
        process_ids = request.data.get("process_ids", [])
        operator_id = request.data.get("operator")
        department_id = request.data.get("department")
        try:
            result = WorkOrderProcessService.batch_start(
                process_ids=process_ids,
                user=request.user,
                operator_id=operator_id,
                department_id=department_id,
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        return APIResponse.success(data=result)

    @action(detail=True, methods=["post"])
    def reassign_tasks(self, request, pk=None):
        """批量重新分派工序的所有任务到新部门/操作员

        使用场景：
        - 工序自动分派后，发现部门无法处理，需要整体调整为外协
        - 批量调整工序下所有任务的分派
        - 例如：裱坑工序从包装车间调整为外协车间

        请求参数：
        - assigned_department: 新分派部门ID（可选）
        - assigned_operator: 新分派操作员ID（可选，清空传null）
        - reason: 调整原因（必填）
        - notes: 备注（可选）
        - update_process_department: 是否同时更新工序级别的部门（默认false）
        """
        work_order_process = self.get_object()
        department_id = request.data.get("assigned_department")
        operator_id = request.data.get("assigned_operator")
        reason = request.data.get("reason", "")
        notes = request.data.get("notes", "")
        update_process_department = request.data.get("update_process_department", False)
        try:
            result = WorkOrderProcessService.reassign_tasks(
                work_order_process=work_order_process,
                user=request.user,
                department_id=department_id,
                operator_id=operator_id,
                reason=reason,
                notes=notes,
                update_process_department=update_process_department,
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        serializer = self.get_serializer(work_order_process)
        return APIResponse.success(data={
                **serializer.data,
                "message": f"成功调整 {result['updated_tasks_count']} 个任务的分派",
                "updated_tasks_count": result["updated_tasks_count"],
                "total_tasks_count": result["total_tasks_count"],
            }
        )
