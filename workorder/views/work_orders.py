"""
WorkOrder 视图集

核心业务视图集：施工单相关 API。
action 方法已按职责拆分到 work_order_mixins.py。
"""

import logging

from django.db.models import Count, Q
from django_filters import CharFilter, DateFilter, FilterSet, NumberFilter
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import filters, permissions, serializers, status, viewsets
from workorder.response import APIResponse
from workorder.docs.work_orders import work_order_docs
from workorder.schema import standard_error_response, standard_success_response

logger = logging.getLogger(__name__)

from ..models.core import WorkOrder
from ..permissions import WorkOrderDataPermission
from ..permission_utils import PermissionCache
from ..permissions.permission_utils import is_manager_user, is_sales_user
from ..serializers.core import (
    WorkOrderCreateUpdateSerializer,
    WorkOrderDetailSerializer,
    WorkOrderListSerializer,
)
from ..throttling import ApprovalRateThrottle, CreateRateThrottle
from .base_viewsets import BaseViewSet
from .work_order_mixins import (
    WorkOrderLifecycleMixin,
    WorkOrderReportingMixin,
    WorkOrderSalesMixin,
    WorkOrderSyncMixin,
)


class WorkOrderFilterSet(FilterSet):
    approval_status = CharFilter(method="filter_approval_status")
    customer_name = CharFilter(field_name="customer__name", lookup_expr="icontains")
    product = NumberFilter(method="filter_product")
    process = NumberFilter(method="filter_process")
    sales_order = NumberFilter(field_name="sales_order")
    order_date_after = DateFilter(field_name="order_date", lookup_expr="gte")
    order_date_before = DateFilter(field_name="order_date", lookup_expr="lte")
    delivery_date_after = DateFilter(field_name="delivery_date", lookup_expr="gte")
    delivery_date_before = DateFilter(field_name="delivery_date", lookup_expr="lte")
    actual_delivery_date_after = DateFilter(
        field_name="actual_delivery_date", lookup_expr="gte"
    )
    actual_delivery_date_before = DateFilter(
        field_name="actual_delivery_date", lookup_expr="lte"
    )
    created_at_after = DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_at_before = DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = WorkOrder
        fields = [
            "status",
            "priority",
            "customer",
            "manager",
            "approval_status",
            "customer_name",
            "product",
            "process",
            "sales_order",
        ]

    def filter_product(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(products__product_id=value).distinct()

    def filter_process(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(order_processes__process_id=value).distinct()

    def filter_approval_status(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(approval_status=value)


@extend_schema_view(
    list=extend_schema(
        tags=["施工单"],
        summary="获取施工单列表",
        description="返回分页的施工单列表，支持按客户、状态、优先级等条件筛选。",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=standard_success_response("WorkOrderListResponse"),
                description="施工单列表",
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="分页列表返回",
                        value={
                            "success": True,
                            "code": 200,
                            "message": "操作成功",
                            "data": {
                                "count": 1,
                                "next": None,
                                "previous": None,
                                "results": [
                                    {
                                        "id": 1,
                                        "order_number": "WO20260302001",
                                        "customer": 3,
                                        "customer_name": "示例客户",
                                        "salesperson_name": "李四",
                                        "product_name": "礼盒",
                                        "quantity": 1000,
                                        "unit": "件",
                                        "status": "pending",
                                        "status_display": "待开始",
                                        "priority": "normal",
                                        "priority_display": "普通",
                                        "order_date": "2026-03-01",
                                        "delivery_date": "2026-03-10",
                                        "production_quantity": 1000,
                                        "manager": 5,
                                        "manager_name": "张三",
                                        "progress_percentage": 0,
                                        "approval_status": "pending",
                                        "approval_status_display": "待审核",
                                        "created_at": "2026-03-02T09:00:00+08:00",
                                    }
                                ],
                            },
                            "timestamp": "2026-03-02T09:00:00+08:00",
                        },
                        response_only=True,
                    )
                ],
            )
        },
    ),
    create=extend_schema(
        tags=["施工单"],
        summary="创建施工单",
        description="创建新的施工单，自动生成所有工序的任务。",
        examples=[
            OpenApiExample(
                name="示例请求",
                summary="创建施工单请求体",
                value={
                    "customer": 3,
                    "priority": "normal",
                    "order_date": "2026-03-01",
                    "delivery_date": "2026-03-10",
                    "production_quantity": 1000,
                    "notes": "客户加急，请优先排产",
                    "products_data": [
                        {
                            "product": 12,
                            "quantity": 1000,
                            "unit": "件",
                            "specification": "210x285mm",
                            "sort_order": 1,
                        }
                    ],
                    "processes": [1, 2, 3],
                    "artworks": [8],
                },
                request_only=True,
            )
        ],
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                response=standard_success_response(
                    "WorkOrderCreateResponse", WorkOrderDetailSerializer
                ),
                description="创建成功",
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="创建成功返回",
                        value={
                            "success": True,
                            "code": 201,
                            "message": "操作成功",
                            "data": {
                                "id": 1,
                                "order_number": "WO20260302001",
                                "customer": 3,
                                "status": "pending",
                                "priority": "normal",
                                "order_date": "2026-03-01",
                                "delivery_date": "2026-03-10",
                                "production_quantity": 1000,
                                "notes": "客户加急，请优先排产",
                                "created_at": "2026-03-02T09:00:00+08:00",
                            },
                            "timestamp": "2026-03-02T09:00:00+08:00",
                        },
                        response_only=True,
                    )
                ],
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                response=standard_error_response("WorkOrderCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
    retrieve=extend_schema(
        tags=["施工单"],
        summary="获取施工单详情",
        description="获取施工单的完整信息，包括关联的任务、产品和工序。",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=standard_success_response(
                    "WorkOrderDetailResponse", WorkOrderDetailSerializer
                ),
                description="施工单详情",
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="详情返回（节选）",
                        value={
                            "success": True,
                            "code": 200,
                            "message": "操作成功",
                            "data": {
                                "id": 1,
                                "order_number": "WO20260302001",
                                "customer": 3,
                                "customer_name": "示例客户",
                                "status": "pending",
                                "status_display": "待开始",
                                "priority": "normal",
                                "priority_display": "普通",
                                "order_date": "2026-03-01",
                                "delivery_date": "2026-03-10",
                                "products": [
                                    {
                                        "id": 21,
                                        "product": 12,
                                        "product_name": "礼盒",
                                        "quantity": 1000,
                                        "unit": "件",
                                    }
                                ],
                                "order_processes": [
                                    {
                                        "id": 31,
                                        "process_name": "印刷",
                                        "status": "pending",
                                        "status_display": "待开始",
                                    }
                                ],
                            },
                            "timestamp": "2026-03-02T09:00:00+08:00",
                        },
                        response_only=True,
                    )
                ],
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                response=standard_error_response("WorkOrderNotFoundResponse"),
                description="施工单不存在",
            ),
        },
    ),
)
@work_order_docs
class WorkOrderViewSet(
    WorkOrderLifecycleMixin,
    WorkOrderReportingMixin,
    WorkOrderSalesMixin,
    WorkOrderSyncMixin,
    BaseViewSet,
):
    """施工单视图集"""

    queryset = WorkOrder.objects.all()
    permission_classes = [WorkOrderDataPermission]  # 使用细粒度数据权限
    filterset_class = WorkOrderFilterSet
    search_fields = [
        "order_number",
        "products__product__name",
        "products__product__code",
        "customer__name",
        "sales_order__order_number",
        "manager__username",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "order_date",
        "delivery_date",
        "actual_delivery_date",
        "order_number",
        "customer__name",
        "customer__salesperson__username",
        "products__product__name",
        "status",
        "priority",
        "approval_status",
        "production_quantity",
        "defective_quantity",
        "total_amount",
        "manager__username",
        "approved_at",
        "sales_order__order_number",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return WorkOrderListSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return WorkOrderCreateUpdateSerializer
        return WorkOrderDetailSerializer

    def update(self, request, *args, **kwargs):
        """重写update方法以捕获详细错误信息（P1 优化：使用日志记录）"""
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            import logging
            import traceback

            logger = logging.getLogger(__name__)
            logger.error(f"Error in WorkOrderViewSet.update: {str(e)}", exc_info=True)
            raise

    def get_queryset(self):
        """根据用户权限过滤查询集，使用查询优化器提升性能"""
        from ..services.query_optimizer import QueryCache, QueryOptimizer

        # 使用查询优化器获取基础查询集
        queryset = QueryOptimizer.optimize_workorder_queryset(
            super().get_queryset(), include_details=False  # 列表视图不需要详细信息
        )

        user = self.request.user
        cache_key = f"workorder_queryset_{user.id}_{user.is_superuser}"

        # 管理员和经理可以查看所有数据
        if user.is_superuser or is_manager_user(user):
            return queryset

        # 使用缓存优化权限查询
        def get_filtered_queryset():
            if is_sales_user(user):
                return queryset.filter(customer__salesperson=user)

            elif user.has_perm("workorder.change_workorder"):
                department_scope = PermissionCache.get_user_department_scope(user)
                if department_scope:
                    # 使用优化的子查询，添加 select_related 优化跨表查询性能
                    from ..models.core import WorkOrderTask

                    work_order_ids = (
                        WorkOrderTask.objects.filter(
                            assigned_department_id__in=department_scope
                        )
                        .select_related(
                            "work_order_process"  # 优化跨表查询，避免N+1问题
                        )
                        .values_list("work_order_process__work_order_id", flat=True)
                        .distinct()
                    )
                    return queryset.filter(id__in=work_order_ids)
                else:
                    return queryset.filter(created_by=user)

            else:
                return queryset.filter(created_by=user)

        return QueryCache.get_cached_queryset(
            cache_key, get_filtered_queryset, timeout=300
        )

    def perform_create(self, serializer):
        # 自动设置创建人和制表人为当前用户
        serializer.save(created_by=self.request.user, manager=self.request.user)

