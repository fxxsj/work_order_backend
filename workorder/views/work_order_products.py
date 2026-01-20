"""
WorkOrderProduct 视图集
"""

"""
核心业务视图集

包含施工单、工序、任务、产品、物料、日志等核心业务视图集。
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import FilterSet, NumberFilter, CharFilter
from django.db.models import Q, Count, Sum, Max, Avg, F
from django.db import models
from django.utils import timezone
from decimal import Decimal

from ..permissions import (
    WorkOrderProcessPermission,
    WorkOrderMaterialPermission,
    WorkOrderTaskPermission,
    WorkOrderDataPermission
)
from ..export_utils import export_work_orders, export_tasks
from ..permissions import SuperuserFriendlyModelPermissions
# P1 优化: 导入自定义速率限制
from ..throttling import ApprovalRateThrottle, ExportRateThrottle, CreateRateThrottle

from ..models.base import Customer, Department, Process
from ..models.products import Product, ProductMaterial
from ..models.materials import Material
from ..models.core import (
    WorkOrder, WorkOrderProcess, WorkOrderMaterial,
    WorkOrderProduct, ProcessLog, WorkOrderTask
)
from ..models.assets import Artwork, Die

from ..serializers.base import ProcessSerializer
from ..serializers.core import (
    WorkOrderListSerializer,
    WorkOrderDetailSerializer,
    WorkOrderCreateUpdateSerializer,
    WorkOrderProcessSerializer,
    WorkOrderProcessUpdateSerializer,
    WorkOrderMaterialSerializer,
    WorkOrderProductSerializer,
    ProcessLogSerializer,
    WorkOrderTaskSerializer
)



class WorkOrderProductViewSet(viewsets.ModelViewSet):
    """施工单产品视图集"""
    queryset = WorkOrderProduct.objects.select_related('product', 'work_order')
    serializer_class = WorkOrderProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['work_order', 'product']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['work_order', 'sort_order']


