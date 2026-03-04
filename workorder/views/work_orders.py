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
from django.db.models import Avg, Count, F, Max, Q, Sum
from django.utils import timezone
from django_filters import CharFilter, FilterSet, NumberFilter
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from workorder.response import APIResponse
from workorder.docs.work_orders import (
    draft_task_bulk_update_docs,
    draft_task_docs,
    work_order_add_material_docs,
    work_order_add_process_docs,
    work_order_approve_docs,
    work_order_docs,
    work_order_export_docs,
    work_order_request_reapproval_docs,
    work_order_resubmit_docs,
    work_order_statistics_docs,
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
    DraftTaskSerializer,
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
from ..services.task_sync_service import TaskSyncService
from ..services.service_errors import ServiceError
from ..services.work_order_service import WorkOrderService

# P1 优化: 导入自定义速率限制
from ..throttling import ApprovalRateThrottle, CreateRateThrottle, ExportRateThrottle
from .base_viewsets import BaseViewSet


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
        description="创建新的施工单，自动生成所有工序的草稿任务。",
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
    filterset_fields = ["status", "priority", "customer", "manager", "approval_status"]
    search_fields = [
        "order_number",
        "products__product__name",
        "products__product__code",
        "customer__name",
    ]
    ordering_fields = ["created_at", "order_date", "delivery_date", "order_number"]
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

        # 管理员可以查看所有数据
        if user.is_superuser:
            return queryset

        # 使用缓存优化权限查询
        def get_filtered_queryset():
            if user.groups.filter(name="业务员").exists():
                return queryset.filter(customer__salesperson=user)

            elif user.has_perm("workorder.change_workorder"):
                user_departments = (
                    user.profile.departments.all() if hasattr(user, "profile") else []
                )
                if user_departments:
                    # 使用优化的子查询，添加 select_related 优化跨表查询性能
                    from ..models.core import WorkOrderTask

                    work_order_ids = (
                        WorkOrderTask.objects.filter(
                            assigned_department__in=user_departments
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
        work_order = serializer.save(created_by=self.request.user, manager=self.request.user)
        try:
            from ..services.task_generation import DraftTaskGenerationService

            DraftTaskGenerationService.generate_draft_tasks(work_order)
        except Exception as e:
            logger.warning(
                f"施工单 {work_order.order_number} 自动生成草稿任务失败：{str(e)}"
            )

    def destroy(self, request, *args, **kwargs):
        """删除施工单时处理级联删除验证和日志记录

        确保删除施工单时，所有关联的草稿任务也被正确删除，无孤立任务残留。
        """
        from ..models.core import WorkOrderTask

        work_order = self.get_object()

        # 在删除前统计草稿任务数量
        draft_tasks_before = WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order, status="draft"
        ).count()

        # 记录删除前的关联对象数量
        processes_count = work_order.order_processes.count()
        total_tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order
        ).count()

        logger.info(
            f"准备删除施工单 {work_order.order_number}: "
            f"{processes_count} 个工序, {total_tasks} 个任务 (其中 {draft_tasks_before} 个草稿任务)"
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

    @action(detail=True, methods=["post"], throttle_classes=[ApprovalRateThrottle])
    @work_order_approve_docs
    def approve(self, request, pk=None):
        """业务员审核施工单（完善版 - P1 优化：添加速率限制和输入验证）"""
        work_order = self.get_object()
        approval_status = request.data.get("approval_status")
        approval_comment = request.data.get("approval_comment", "")
        rejection_reason = request.data.get("rejection_reason", "")
        try:
            work_order = WorkOrderService.approve(
                work_order=work_order,
                user=request.user,
                approval_status=approval_status,
                approval_comment=approval_comment,
                rejection_reason=rejection_reason,
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        serializer = self.get_serializer(work_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @work_order_resubmit_docs
    def resubmit_for_approval(self, request, pk=None):
        """重新提交审核（审核拒绝后使用）"""
        work_order = self.get_object()
        try:
            work_order = WorkOrderService.resubmit_for_approval(
                work_order=work_order, user=request.user
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        serializer = self.get_serializer(work_order)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    @work_order_request_reapproval_docs
    def request_reapproval(self, request, pk=None):
        """请求重新审核（审核通过后发现错误需要修改）

        使用场景：
        - 审核通过后发现需要修改核心字段（产品、工序、版等）
        - 审核通过后发现需要添加工序
        - 审核通过后发现数据错误需要修正

        流程：
        1. 检查权限（只有创建人或制表人可以请求重新审核）
        2. 检查状态（只有已审核通过的施工单可以请求重新审核）
        3. 重置审核状态为 pending
        4. 重置施工单状态为 pending（如果已开始，需要重置）
        5. 通知原审核人
        """
        work_order = self.get_object()
        request_reason = request.data.get("reason", "")
        try:
            original_approver = WorkOrderService.request_reapproval(
                work_order=work_order, user=request.user, reason=request_reason
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        serializer = self.get_serializer(work_order)
        return APIResponse.success(
            data={
                **serializer.data,
                "message": "重新审核请求已提交，已通知原审核人",
                "original_approver": (
                    original_approver.username if original_approver else None),
            }
        )

    @action(detail=False, methods=["get"])
    @work_order_statistics_docs
    def statistics(self, request):
        """统计数据（增强版：包含任务统计和生产效率分析）"""
        from datetime import timedelta

        queryset = self.filter_queryset(self.get_queryset())

        total_count = queryset.count()

        # 状态统计：确保所有状态都有数据，即使数量为0
        status_stats = list(
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )
        # 确保所有状态都包含在内
        all_statuses = ["pending", "in_progress", "paused", "completed", "cancelled"]
        status_dict = {item["status"]: item["count"] for item in status_stats}
        status_statistics = [
            {"status": status, "count": status_dict.get(status, 0)}
            for status in all_statuses
        ]

        # 优先级统计：确保所有优先级都有数据，即使数量为0
        priority_stats = list(
            queryset.values("priority").annotate(count=Count("id")).order_by("priority")
        )
        # 确保所有优先级都包含在内
        all_priorities = ["low", "normal", "high", "urgent"]
        priority_dict = {item["priority"]: item["count"] for item in priority_stats}
        priority_statistics = [
            {"priority": priority, "count": priority_dict.get(priority, 0)}
            for priority in all_priorities
        ]

        # 即将到期的订单（7天内）
        upcoming_deadline = queryset.filter(
            delivery_date__lte=timezone.now().date() + timedelta(days=7),
            status__in=["pending", "in_progress"],
        ).count()

        # 未审核施工单数量（仅业务员可见，只统计自己负责的）
        pending_approval_count = 0
        if request.user.groups.filter(name="业务员").exists():
            pending_approval_count = queryset.filter(
                approval_status="pending", customer__salesperson=request.user
            ).count()

        # ========== 新增：任务统计 ==========
        from ..models.core import WorkOrderProcess, WorkOrderTask

        # 任务总数统计
        all_tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order__in=queryset
        )
        task_total_count = all_tasks.count()

        # 任务状态统计
        task_status_stats = list(
            all_tasks.values("status").annotate(count=Count("id")).order_by("status")
        )
        all_task_statuses = ["pending", "in_progress", "completed", "cancelled"]
        task_status_dict = {item["status"]: item["count"] for item in task_status_stats}
        task_status_statistics = [
            {"status": status, "count": task_status_dict.get(status, 0)}
            for status in all_task_statuses
        ]

        # 任务类型统计
        task_type_stats = list(
            all_tasks.values("task_type")
            .annotate(count=Count("id"))
            .order_by("task_type")
        )
        task_type_statistics = [
            {"task_type": item["task_type"], "count": item["count"]}
            for item in task_type_stats
        ]

        # 按部门统计任务
        task_dept_stats = list(
            all_tasks.filter(assigned_department__isnull=False)
            .values("assigned_department__name")
            .annotate(
                count=Count("id"), completed=Count("id", filter=Q(status="completed"))
            )
            .order_by("-count")
        )
        task_department_statistics = [
            {
                "department": item["assigned_department__name"],
                "total": item["count"],
                "completed": item["completed"],
                "completion_rate": (
                    round(item["completed"] / item["count"] * 100, 2)
                    if item["count"] > 0
                    else 0
                ),
            }
            for item in task_dept_stats
        ]

        # ========== 新增：生产效率分析 ==========

        # 工序完成率统计
        all_processes = WorkOrderProcess.objects.filter(work_order__in=queryset)
        process_total = all_processes.count()
        process_completed = all_processes.filter(status="completed").count()
        process_completion_rate = (
            round(process_completed / process_total * 100, 2)
            if process_total > 0
            else 0
        )

        # 平均完成时间（已完成工序）
        completed_processes = all_processes.filter(
            status="completed",
            actual_start_time__isnull=False,
            actual_end_time__isnull=False,
        )
        avg_completion_time = None
        if completed_processes.exists():
            # 计算平均完成时间（小时）
            completion_times = []
            for process in completed_processes:
                if process.actual_start_time and process.actual_end_time:
                    delta = process.actual_end_time - process.actual_start_time
                    completion_times.append(delta.total_seconds() / 3600)  # 转换为小时

            if completion_times:
                avg_completion_time = round(
                    sum(completion_times) / len(completion_times), 2
                )

        # 任务完成率统计
        task_completed = all_tasks.filter(status="completed").count()
        task_completion_rate = (
            round(task_completed / task_total_count * 100, 2)
            if task_total_count > 0
            else 0
        )

        # 不良品率统计（已完成任务）
        completed_tasks = all_tasks.filter(status="completed")
        total_production_quantity = completed_tasks.aggregate(
            total=Sum("production_quantity", default=0)
        )["total"]
        total_defective_quantity = completed_tasks.aggregate(
            total=Sum("quantity_defective", default=0)
        )["total"]
        defective_rate = (
            round(total_defective_quantity / total_production_quantity * 100, 2)
            if total_production_quantity > 0
            else 0
        )

        # 按客户统计
        customer_stats = list(
            queryset.values("customer__name")
            .annotate(
                count=Count("id"), completed=Count("id", filter=Q(status="completed"))
            )
            .order_by("-count")[:10]  # 前10个客户
        )
        customer_statistics = [
            {
                "customer": item["customer__name"],
                "total": item["count"],
                "completed": item["completed"],
                "completion_rate": (
                    round(item["completed"] / item["count"] * 100, 2)
                    if item["count"] > 0
                    else 0
                ),
            }
            for item in customer_stats
        ]

        # 按产品统计
        from ..models.core import WorkOrderProduct

        product_stats = list(
            WorkOrderProduct.objects.filter(work_order__in=queryset)
            .values("product__name", "product__code")
            .annotate(
                count=Count("work_order", distinct=True), total_quantity=Sum("quantity")
            )
            .order_by("-count")[:10]  # 前10个产品
        )
        product_statistics = [
            {
                "product_name": item["product__name"],
                "product_code": item["product__code"],
                "order_count": item["count"],
                "total_quantity": item["total_quantity"],
            }
            for item in product_stats
        ]

        return APIResponse.success(data={
                # 基础统计
                "total_count": total_count,
                "status_statistics": status_statistics,
                "priority_statistics": priority_statistics,
                "upcoming_deadline_count": upcoming_deadline,
                "pending_approval_count": pending_approval_count,
                # 任务统计
                "task_statistics": {
                    "total_count": task_total_count,
                    "status_statistics": task_status_statistics,
                    "type_statistics": task_type_statistics,
                    "department_statistics": task_department_statistics,
                    "completion_rate": task_completion_rate,
                },
                # 生产效率分析
                "efficiency_analysis": {
                    "process_completion_rate": process_completion_rate,
                    "process_total": process_total,
                    "process_completed": process_completed,
                    "avg_completion_time_hours": avg_completion_time,
                    "task_completion_rate": task_completion_rate,
                    "defective_rate": defective_rate,
                    "total_production_quantity": total_production_quantity,
                    "total_defective_quantity": total_defective_quantity,
                },
                # 业务分析
                "business_analysis": {
                    "customer_statistics": customer_statistics,
                    "product_statistics": product_statistics,
                },
            })

    @action(detail=False, methods=["get"], throttle_classes=[ExportRateThrottle])
    @work_order_export_docs
    def export(self, request):
        """导出施工单列表到 Excel（P1 优化：添加速率限制）"""
        # 权限检查：需要查看权限
        if not request.user.has_perm("workorder.view_workorder"):
            return APIResponse.error("您没有权限导出施工单数据", code=status.HTTP_400_BAD_REQUEST)

        # 获取过滤后的查询集（使用 get_queryset 确保权限过滤）
        queryset = self.filter_queryset(self.get_queryset())

        # 记录导出日志（可选）
        # 这里可以添加导出日志记录功能

        # 导出 Excel
        filename = request.query_params.get("filename")
        return export_work_orders(queryset, filename)

    @action(detail=True, methods=["post"])
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
            return APIResponse.error("process_ids 必须是列表", code=status.HTTP_400_BAD_REQUEST)

        # 获取当前工序ID列表
        old_process_ids = list(work_order.order_processes.values_list("id", flat=True))

        # 验证施工单是否已审核
        if work_order.approval_status == "approved":
            return APIResponse.error("已审核的施工单不能修改工序", code=status.HTTP_400_BAD_REQUEST)

        # 调用 TaskSyncService 计算预览
        preview = TaskSyncService.preview_sync(
            work_order, old_process_ids, new_process_ids
        )

        return APIResponse.error("process_ids 必须是列表", code=status.HTTP_400_BAD_REQUEST, data={"preview": preview})

    @action(detail=True, methods=["post"])
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
                "message": "同步完成：已删除 5 个草稿任务，新增 3 个草稿任务"
            }
        }
        """
        work_order = self.get_object()
        new_process_ids = request.data.get("process_ids", [])

        # 验证输入
        if not isinstance(new_process_ids, list):
            return APIResponse.error("process_ids 必须是列表", code=status.HTTP_400_BAD_REQUEST)

        # 获取当前工序ID列表
        old_process_ids = list(work_order.order_processes.values_list("id", flat=True))

        # 验证施工单是否已审核
        if work_order.approval_status == "approved":
            return APIResponse.error("已审核的施工单不能同步任务", code=status.HTTP_400_BAD_REQUEST)

        # 要求确认标志（防止误操作）
        if not request.data.get("confirmed"):
            return APIResponse.error("需要确认后才能执行同步，请设置 confirmed=true", code=status.HTTP_400_BAD_REQUEST)

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

        # 检查是否有变化
        has_changes = set(current_process_ids) != set(stored_process_ids)

        # 检查是否可以同步（未审核的施工单才能同步）
        can_sync = work_order.approval_status != "approved"

        return APIResponse.success(data={
                "sync_needed": has_changes and can_sync,
                "current_process_ids": current_process_ids,
                "can_sync": can_sync,
            })


@draft_task_docs
class DraftTaskViewSet(BaseViewSet):
    """草稿任务视图集（允许编辑和删除草稿状态的任务）"""

    serializer_class = DraftTaskSerializer
    permission_classes = [WorkOrderTaskPermission]
    filterset_fields = ["status", "task_type", "work_order_process"]
    search_fields = ["work_content", "description"]
    ordering_fields = ["created_at", "production_quantity", "estimated_hours"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """只返回草稿状态的任务"""
        if getattr(self, "swagger_fake_view", False):
            return WorkOrderTask.objects.none()

        user = self.request.user

        # 获取草稿任务
        queryset = WorkOrderTask.objects.filter(status="draft").select_related(
            "work_order_process__work_order__customer",
            "work_order_process__process",
            "assigned_department",
            "assigned_operator",
        )

        # 权限过滤：基于施工单的数据权限
        if not user.is_superuser:
            # 管理员可以看到所有草稿任务
            if not user.has_perm("workorder.manage_all_workorders"):
                # 普通用户只能看到自己创建的施工单的草稿任务
                queryset = queryset.filter(
                    work_order_process__work_order__created_by=user
                )

        return queryset

    def perform_update(self, serializer):
        """更新前验证"""
        instance = self.get_object()

        # 确保任务仍为草稿状态
        if instance.status != "draft":
            raise serializers.ValidationError(
                "只能编辑草稿状态的任务。当前任务状态为：{}".format(
                    instance.get_status_display()
                )
            )

        # 检查施工单是否已审核
        work_order = instance.work_order_process.work_order
        if work_order.approval_status == "approved":
            raise serializers.ValidationError("已审核的施工单不允许编辑草稿任务")

        # 保存更新
        serializer.save(status="draft")

    def perform_destroy(self, instance):
        """删除前验证"""
        # 确保任务仍为草稿状态
        if instance.status != "draft":
            raise serializers.ValidationError(
                "只能删除草稿状态的任务。当前任务状态为：{}".format(
                    instance.get_status_display()
                )
            )

        # 检查施工单是否已审核
        work_order = instance.work_order_process.work_order
        if work_order.approval_status == "approved":
            raise serializers.ValidationError("已审核的施工单不允许删除草稿任务")

        # 删除任务
        instance.delete()

    @action(detail=False, methods=["patch"])
    @draft_task_bulk_update_docs
    def bulk_update(self, request):
        """批量更新草稿任务

        请求体格式：
        {
            "task_ids": [1, 2, 3],
            "updates": {
                "estimated_hours": 8,
                "description": "批量更新的描述"
            }
        }
        """
        task_ids = request.data.get("task_ids", [])
        updates = request.data.get("updates", {})

        if not task_ids:
            return APIResponse.error("请提供要更新的任务ID列表", code=status.HTTP_400_BAD_REQUEST)

        if not updates:
            return APIResponse.error("请提供要更新的字段", code=status.HTTP_400_BAD_REQUEST)

        # 获取任务并验证权限
        queryset = self.get_queryset().filter(id__in=task_ids)

        if queryset.count() != len(task_ids):
            return APIResponse.error("部分任务不存在或无权访问", code=status.HTTP_404_NOT_FOUND)

        # 批量更新
        updated_count = 0
        for task in queryset:
            # 验证任务状态
            if task.status != "draft":
                continue

            # 验证施工单状态
            work_order = task.work_order_process.work_order
            if work_order.approval_status == "approved":
                continue

            # 更新字段
            for field, value in updates.items():
                if hasattr(task, field):
                    setattr(task, field, value)

            task.status = "draft"  # 确保状态保持为 draft
            task.save()
            updated_count += 1

        return APIResponse.success(data={
                "message": f"成功更新 {updated_count} 个草稿任务",
                "updated_count": updated_count,
                "total_requested": len(task_ids),
            }
        )
