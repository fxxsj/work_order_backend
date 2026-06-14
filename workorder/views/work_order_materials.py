"""
WorkOrderMaterial 视图集
"""

"""
核心业务视图集

包含施工单、工序、任务、产品、物料、日志等核心业务视图集。
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from workorder.response import APIResponse
from workorder.docs.work_orders_items import work_order_material_docs

from ..models.core import WorkOrderMaterial
from ..permissions import WorkOrderMaterialPermission
from ..serializers.core import WorkOrderMaterialSerializer
from ..services.work_order_material_service import WorkOrderMaterialService
from ..services.service_errors import ServiceError


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
        """确认物料开料完成。"""
        wom = self.get_object()
        try:
            WorkOrderMaterialService.confirm_cutting(
                wom=wom,
                user=request.user,
                cut_quantity=request.data.get("cut_quantity"),
                wastage_quantity=request.data.get("wastage_quantity"),
                notes=request.data.get("notes", ""),
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        serializer = self.get_serializer(wom)
        return APIResponse.success(
            data=serializer.data,
            message="物料开料确认成功，相关任务已更新",
        )
