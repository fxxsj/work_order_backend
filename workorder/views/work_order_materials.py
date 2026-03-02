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
    filterset_fields = ["work_order", "material"]
