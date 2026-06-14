"""
WorkOrder 视图集
"""

"""
核心业务视图集

包含施工单、工序、任务、产品、物料、日志等核心业务视图集。
"""

import logging
from decimal import Decimal

from django.db import models
from django.db.models import Count, Q, Sum
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
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from workorder.response import APIResponse
from workorder.docs.work_orders import (
    work_order_add_material_docs,
    work_order_add_process_docs,
    work_order_docs,
    work_order_export_docs,
    work_order_statistics_docs,
    work_order_summary_docs,
    work_order_sync_check_docs,
    work_order_sync_execute_docs,
    work_order_sync_preview_docs,
    work_order_update_status_docs,
)
from workorder.schema import standard_error_response, standard_success_response

logger = logging.getLogger(__name__)

from ..export_utils import export_tasks, export_work_orders
from ..models.assets import Artwork, Die
from ..models.base import Customer, Department, Process
from ..models.core import (
    ProcessLog,
    WorkOrder,
    WorkOrderMaterial,
    WorkOrderProcess,
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
from ..permission_utils import PermissionCache
from ..permissions.permission_utils import is_manager_user, is_sales_user
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
from ..services.work_order_statistics_service import (
    SalesOrderCandidateService,
    WorkOrderStatisticsService,
)
from ..services.task_sync_service import TaskSyncService
from ..services.service_errors import ServiceError
from ..services.work_order_service import WorkOrderService

# P1 优化: 导入自定义速率限制
from ..throttling import ApprovalRateThrottle, CreateRateThrottle, ExportRateThrottle
from .base_viewsets import BaseViewSet
from .sales import _scope_sales_orders


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
            200: OpenApiResponse(
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
            201: OpenApiResponse(
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
            400: OpenApiResponse(
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
            200: OpenApiResponse(
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
            404: OpenApiResponse(
                response=standard_error_response("WorkOrderNotFoundResponse"),
                description="施工单不存在",
            ),
        },
    ),
)
@work_order_docs
class WorkOrderViewSet(BaseViewSet):
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

    def destroy(self, request, *args, **kwargs):
        """删除施工单时处理级联删除验证和日志记录

        确保删除施工单时，所有关联的任务也被正确删除，无孤立任务残留。
        """
        from ..models.core import WorkOrderTask

        work_order = self.get_object()

        # 记录删除前的关联对象数量
        processes_count = work_order.order_processes.count()
        total_tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order
        ).count()

        logger.info(
            f"准备删除施工单 {work_order.order_number}: "
            f"{processes_count} 个工序, {total_tasks} 个任务"
        )

        # 执行删除（会自动级联删除工序和任务）
        response = super().destroy(request, *args, **kwargs)

        # 验证级联删除是否成功（检查无孤立任务）
        orphaned_tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order__isnull=True
        ).count()

        if orphaned_tasks > 0:
            logger.warning(
                f"删除施工单 {work_order.order_number} 后发现 {orphaned_tasks} 个孤立任务，"
                f"这可能表示数据完整性问题"
            )
        else:
            logger.info(
                f"成功删除施工单 {work_order.order_number} 及其所有关联数据，"
                f"无孤立任务残留"
            )

        return response

    @action(detail=True, methods=["post"])
    @work_order_add_process_docs
    def add_process(self, request, pk=None):
        """为施工单添加工序"""
        work_order = self.get_object()
        process_id = request.data.get("process_id")
        sequence = request.data.get("sequence", 0)

        try:
            work_order_process = WorkOrderService.add_process(
                work_order=work_order, process_id=process_id, sequence=sequence
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        serializer = WorkOrderProcessSerializer(work_order_process)
        return APIResponse.success(data=serializer.data, code=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @work_order_add_material_docs
    def add_material(self, request, pk=None):
        """为施工单添加物料"""
        work_order = self.get_object()
        material_id = request.data.get("material_id")
        notes = request.data.get("notes", "")

        try:
            work_order_material = WorkOrderService.add_material(
                work_order=work_order, material_id=material_id, notes=notes
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        serializer = WorkOrderMaterialSerializer(work_order_material)
        return APIResponse.success(data=serializer.data, code=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @work_order_update_status_docs
    def update_status(self, request, pk=None):
        """更新施工单状态"""
        work_order = self.get_object()
        new_status = request.data.get("status")

        try:
            work_order = WorkOrderService.update_status(
                work_order=work_order, new_status=new_status
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        serializer = self.get_serializer(work_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=False, methods=["get"])
    @work_order_statistics_docs
    def statistics(self, request):
        """统计数据（增强版：包含任务统计和生产效率分析）"""
        queryset = self.filter_queryset(self.get_queryset())
        data = WorkOrderStatisticsService.get_dashboard_stats(queryset, request.user)
        return APIResponse.success(data=data)

    @action(detail=False, methods=["get"])
    def sales_order_candidates(self, request):
        """返回可关联到施工单的客户订单候选及其可用产品。"""
        exclude_work_order_id = request.query_params.get("exclude_work_order_id")
        try:
            candidates = SalesOrderCandidateService.get_candidates(
                exclude_work_order_id, request.user
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)
        return APIResponse.success(data=candidates)

    @action(detail=False, methods=["get"])
    @work_order_summary_docs
    def summary(self, request):
        """施工单汇总"""
        queryset = self.filter_queryset(self.get_queryset())
        summary = queryset.aggregate(
            total_count=Count("id"),
            pending_count=Count("id", filter=Q(status="pending")),
            in_progress_count=Count("id", filter=Q(status="in_progress")),
            completed_count=Count("id", filter=Q(status="completed")),
            cancelled_count=Count("id", filter=Q(status="cancelled")),
            pending_approval_count=Count("id", filter=Q(approval_status="submitted")),
            approved_count=Count("id", filter=Q(approval_status="approved")),
            rejected_approval_count=Count("id", filter=Q(approval_status="rejected")),
        )
        status_stats = (
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )
        approval_stats = (
            queryset.values("approval_status")
            .annotate(count=Count("id"))
            .order_by("approval_status")
        )
        return APIResponse.success(
            data={
                "summary": summary,
                "by_status": list(status_stats),
                "by_approval_status": list(approval_stats),
            }
        )

    @action(detail=False, methods=["get"], throttle_classes=[ExportRateThrottle])
    @work_order_export_docs
    def export(self, request):
        """导出施工单列表到 Excel（P1 优化：添加速率限制）"""
        # 权限检查：需要查看权限
        if not request.user.has_perm("workorder.view_workorder"):
            return APIResponse.error(
                "您没有权限导出施工单数据",
                code=status.HTTP_403_FORBIDDEN,
            )

        # 获取过滤后的查询集（使用 get_queryset 确保权限过滤）
        queryset = self.filter_queryset(self.get_queryset())

        # 记录导出日志（可选）
        # 这里可以添加导出日志记录功能

        # 导出 Excel
        filename = request.query_params.get("filename")
        return export_work_orders(queryset, filename)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    @work_order_sync_preview_docs
    def sync_tasks_preview(self, request, pk=None):
        """预览任务同步变更（不执行同步）

        接收新的工序ID列表，计算如果执行同步会发生什么变化。
        返回预览信息供用户确认后再执行实际同步。

        请求体格式：
        {
            "process_ids": [1, 2, 3, ...]
        }

        返回格式：
        {
            "preview": {
                "tasks_to_remove": 5,
                "tasks_to_add": 3,
                "removed_process_ids": [4, 5],
                "added_process_ids": [6, 7],
                "affected": true
            }
        }
        """
        work_order = self.get_object()
        new_process_ids = request.data.get("process_ids", [])

        # 验证输入
        if not isinstance(new_process_ids, list):
            return APIResponse.error(
                "process_ids 必须是列表", code=status.HTTP_400_BAD_REQUEST
            )

        # 获取当前工序ID列表
        old_process_ids = list(work_order.order_processes.values_list("id", flat=True))

        # 验证施工单是否已审核
        if work_order.approval_status == "approved":
            return APIResponse.error(
                "已审核的施工单不能修改工序", code=status.HTTP_400_BAD_REQUEST
            )

        # 调用 TaskSyncService 计算预览
        preview = TaskSyncService.preview_sync(
            work_order, old_process_ids, new_process_ids
        )

        return APIResponse.success(data={"preview": preview})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    @work_order_sync_execute_docs
    def sync_tasks_execute(self, request, pk=None):
        """执行任务同步（需要用户确认）

        在用户确认预览后，执行实际的同步操作。
        必须提供 confirmed=true 标志，防止误操作。

        请求体格式：
        {
            "process_ids": [1, 2, 3, ...],
            "confirmed": true
        }

        返回格式：
        {
            "result": {
                "deleted_count": 5,
                "added_count": 3,
                "message": "同步完成：已删除 5 个任务，新增 3 个任务"
            }
        }
        """
        work_order = self.get_object()
        new_process_ids = request.data.get("process_ids", [])

        # 验证输入
        if not isinstance(new_process_ids, list):
            return APIResponse.error(
                "process_ids 必须是列表", code=status.HTTP_400_BAD_REQUEST
            )

        # 获取当前工序ID列表
        old_process_ids = list(work_order.order_processes.values_list("id", flat=True))

        # 验证施工单是否已审核
        if work_order.approval_status == "approved":
            return APIResponse.error(
                "已审核的施工单不能同步任务", code=status.HTTP_400_BAD_REQUEST
            )

        # 要求确认标志（防止误操作）
        if not request.data.get("confirmed"):
            return APIResponse.error(
                "需要确认后才能执行同步，请设置 confirmed=true",
                code=status.HTTP_400_BAD_REQUEST,
            )

        # 执行同步
        try:
            result = TaskSyncService.execute_sync(
                work_order, old_process_ids, new_process_ids
            )
            return APIResponse.success(
                data={
                    "result": result,
                    "message": result.get("message", "任务同步完成"),
                }
            )
        except Exception as e:
            logger.error(f"执行任务同步失败: {str(e)}", exc_info=True)
            return APIResponse.error(
                f"同步失败: {str(e)}",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    @work_order_sync_check_docs
    def check_sync_needed(self, request, pk=None):
        """检查是否需要任务同步

        检测施工单工序是否发生变化，判断是否需要同步任务。
        前端可以在工序更新前后调用此接口，提示用户进行同步。

        查询参数：
        - process_ids: 工序ID列表（逗号分隔），如 "1,2,3"

        返回格式：
        {
            "sync_needed": true,
            "current_process_ids": [1, 2, 3],
            "can_sync": true
        }
        """
        work_order = self.get_object()

        # 获取当前工序ID列表
        current_process_ids = list(
            work_order.order_processes.values_list("id", flat=True)
        )

        # 从查询参数获取前端存储的工序ID列表
        process_ids_str = request.query_params.get("process_ids", "")
        if process_ids_str:
            stored_process_ids = [
                int(pid) for pid in process_ids_str.split(",") if pid.strip()
            ]
        else:
            stored_process_ids = []

        # 检查是否可以同步（未审核的施工单才能同步）
        can_sync = work_order.approval_status != "approved"
        preview = TaskSyncService.preview_sync(
            work_order,
            stored_process_ids or current_process_ids,
            current_process_ids,
        )

        return APIResponse.success(
            data={
                "sync_needed": preview.get("sync_needed", False) and can_sync,
                "current_process_ids": current_process_ids,
                "can_sync": can_sync,
                "preview": preview,
            }
        )
