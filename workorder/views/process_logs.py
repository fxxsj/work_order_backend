"""
ProcessLog 视图集
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from ..models.core import (
    ProcessLog,
)
from ..permissions import (
    SuperuserFriendlyModelPermissions,
)
from ..serializers.core import (
    ProcessLogSerializer,
)
from workorder.docs.process_logs import process_log_docs

# P1 优化: 导入自定义速率限制


@process_log_docs
class ProcessLogViewSet(viewsets.ReadOnlyModelViewSet):
    """工序日志视图集（只读）"""

    queryset = ProcessLog.objects.select_related(
        "work_order_process",
        "work_order_process__work_order",
        "work_order_process__process",
        "operator",
    ).all()
    serializer_class = ProcessLogSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["work_order_process", "log_type", "operator"]
    search_fields = [
        "content",
        "operator__username",
        "work_order_process__work_order__order_number",
        "work_order_process__process__name",
        "work_order_process__process__code",
    ]
    ordering_fields = [
        "created_at",
        "log_type",
        "operator__username",
        "work_order_process__work_order__order_number",
        "work_order_process__process__name",
    ]
    ordering = ["-created_at"]
