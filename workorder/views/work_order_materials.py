"""
WorkOrderMaterial 视图集
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from workorder.response import APIResponse
from workorder.docs.work_orders_items import work_order_material_docs

from ..models.core import WorkOrderMaterial
from ..permissions import WorkOrderMaterialPermission
from ..serializers.core import (
    MaterialPlanCalculateSerializer,
    MaterialPlanInvalidateSerializer,
    WorkOrderMaterialSerializer,
)
from ..services.work_order_material_service import WorkOrderMaterialService
from ._decorators import handle_service_error


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
    @handle_service_error
    def calculate_plan(self, request, pk=None):
        """根据拼版开料尺寸计算原纸计划和采购缺口。"""
        input_serializer = MaterialPlanCalculateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        wom = WorkOrderMaterialService.calculate_plan(
            wom=self.get_object(), **input_serializer.validated_data
        )
        return APIResponse.success(
            data=self.get_serializer(wom).data,
            message="物料计划计算完成",
        )

    @action(detail=True, methods=["post"])
    @handle_service_error
    def confirm_plan(self, request, pk=None):
        """确认物料计划并预留可用库存。"""
        wom = WorkOrderMaterialService.confirm_plan(
            wom=self.get_object(), user=request.user
        )
        return APIResponse.success(
            data=self.get_serializer(wom).data,
            message="物料计划已确认并完成库存预留",
        )

    @action(detail=True, methods=["post"])
    @handle_service_error
    def invalidate_plan(self, request, pk=None):
        """作废物料计划并释放库存预留。"""
        input_serializer = MaterialPlanInvalidateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        wom = WorkOrderMaterialService.invalidate_plan(
            wom=self.get_object(),
            user=request.user,
            reason=input_serializer.validated_data["reason"],
        )
        return APIResponse.success(
            data=self.get_serializer(wom).data,
            message="物料计划已作废，库存预留已释放",
        )

    @action(detail=True, methods=["post"])
    @handle_service_error
    def confirm_cutting(self, request, pk=None):
        """确认物料开料完成。"""
        wom = self.get_object()
        WorkOrderMaterialService.confirm_cutting(
            wom=wom,
            user=request.user,
            cut_quantity=request.data.get("cut_quantity"),
            wastage_quantity=request.data.get("wastage_quantity"),
            notes=request.data.get("notes", ""),
        )
        serializer = self.get_serializer(wom)
        return APIResponse.success(
            data=serializer.data,
            message="物料开料确认成功，相关任务已更新",
        )
