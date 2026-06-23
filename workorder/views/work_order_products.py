"""
WorkOrderProduct 视图集
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from workorder.docs.work_orders_items import work_order_product_docs

from ..models.core import (
    WorkOrderProduct,
)
from ..permissions import (
    WorkOrderProductPermission,
)
from ..serializers.core import (
    WorkOrderProductSerializer,
)

# P1 优化: 导入自定义速率限制


@work_order_product_docs
class WorkOrderProductViewSet(viewsets.ModelViewSet):
    """施工单产品视图集"""

    queryset = WorkOrderProduct.objects.select_related("product", "work_order")
    serializer_class = WorkOrderProductSerializer
    permission_classes = [WorkOrderProductPermission]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["work_order", "product"]
    ordering_fields = ["sort_order", "created_at"]
    ordering = ["work_order", "sort_order"]
