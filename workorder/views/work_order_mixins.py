"""WorkOrderViewSet 的 mixin 拆分。

将生命周期、报表、同步、销售相关 action 分组到独立 mixin，
保持 WorkOrderViewSet 本身只做组合与标准 DRF 覆盖。
"""

import logging

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from workorder.response import APIResponse
from workorder.docs.work_orders import (
    work_order_add_material_docs,
    work_order_add_process_docs,
    work_order_export_docs,
    work_order_statistics_docs,
    work_order_summary_docs,
    work_order_sync_check_docs,
    work_order_sync_execute_docs,
    work_order_sync_preview_docs,
    work_order_update_status_docs,
)
from ..export_utils import export_work_orders
from ..serializers.core import (
    WorkOrderMaterialSerializer,
    WorkOrderProcessSerializer,
)
from ..services.task_sync_service import TaskSyncService
from ..services.work_order_service import WorkOrderService
from ..services.work_order_statistics_service import (
    SalesOrderCandidateService,
    WorkOrderStatisticsService,
)
from ..throttling import ExportRateThrottle
from ._decorators import handle_service_error

logger = logging.getLogger(__name__)


class WorkOrderLifecycleMixin:
    """施工单生命周期相关 action：添加工序/物料、更新状态、删除。"""

    @action(detail=True, methods=["post"])
    @work_order_add_process_docs
    @handle_service_error
    def add_process(self, request, pk=None):
        """为施工单添加工序"""
        work_order = self.get_object()
        process_id = request.data.get("process_id")
        sequence = request.data.get("sequence", 0)
        work_order_process = WorkOrderService.add_process(
            work_order=work_order, process_id=process_id, sequence=sequence
        )
        serializer = WorkOrderProcessSerializer(work_order_process)
        return APIResponse.success(
            data=serializer.data, code=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    @work_order_add_material_docs
    @handle_service_error
    def add_material(self, request, pk=None):
        """为施工单添加物料"""
        work_order = self.get_object()
        material_id = request.data.get("material_id")
        notes = request.data.get("notes", "")
        work_order_material = WorkOrderService.add_material(
            work_order=work_order, material_id=material_id, notes=notes
        )
        serializer = WorkOrderMaterialSerializer(work_order_material)
        return APIResponse.success(
            data=serializer.data, code=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    @work_order_update_status_docs
    @handle_service_error
    def update_status(self, request, pk=None):
        """更新施工单状态"""
        work_order = self.get_object()
        new_status = request.data.get("status")
        work_order = WorkOrderService.update_status(
            work_order=work_order, new_status=new_status
        )
        serializer = self.get_serializer(work_order)
        return APIResponse.success(data=serializer.data)

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


class WorkOrderReportingMixin:
    """施工单报表/统计相关 action。"""

    @action(detail=False, methods=["get"])
    @work_order_statistics_docs
    def statistics(self, request):
        """统计数据（增强版：包含任务统计和生产效率分析）"""

        queryset = self.filter_queryset(self.get_queryset())
        data = WorkOrderStatisticsService.get_dashboard_stats(
            queryset, request.user
        )
        return APIResponse.success(data=data)

    @action(detail=False, methods=["get"])
    @work_order_summary_docs
    def summary(self, request):
        """施工单汇总"""
        from django.db.models import Count, Q

        queryset = self.filter_queryset(self.get_queryset())
        summary = queryset.aggregate(
            total_count=Count("id"),
            pending_count=Count("id", filter=Q(status="pending")),
            in_progress_count=Count("id", filter=Q(status="in_progress")),
            completed_count=Count("id", filter=Q(status="completed")),
            cancelled_count=Count("id", filter=Q(status="cancelled")),
            pending_approval_count=Count(
                "id", filter=Q(approval_status="submitted")
            ),
            approved_count=Count("id", filter=Q(approval_status="approved")),
            rejected_approval_count=Count(
                "id", filter=Q(approval_status="rejected")
            ),
        )
        status_stats = (
            queryset.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
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

    @action(
        detail=False, methods=["get"], throttle_classes=[ExportRateThrottle]
    )
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

        # 导出 Excel
        filename = request.query_params.get("filename")
        return export_work_orders(queryset, filename)


class WorkOrderSalesMixin:
    """施工单与销售订单关联相关 action。"""

    @action(detail=False, methods=["get"])
    @handle_service_error
    def sales_order_candidates(self, request):
        """返回可关联到施工单的客户订单候选及其可用产品。"""
        exclude_work_order_id = request.query_params.get(
            "exclude_work_order_id"
        )
        candidates = SalesOrderCandidateService.get_candidates(
            exclude_work_order_id, request.user
        )
        return APIResponse.success(data=candidates)


class WorkOrderSyncMixin:
    """施工单任务同步相关 action（仅管理员）。"""

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    @work_order_sync_preview_docs
    def sync_tasks_preview(self, request, pk=None):
        """预览任务同步变更（不执行同步）"""
        work_order = self.get_object()
        new_process_ids = request.data.get("process_ids", [])

        if not isinstance(new_process_ids, list):
            return APIResponse.error(
                "process_ids 必须是列表", code=status.HTTP_400_BAD_REQUEST
            )

        old_process_ids = list(
            work_order.order_processes.values_list("id", flat=True)
        )

        if work_order.approval_status == "approved":
            return APIResponse.error(
                "已审核的施工单不能修改工序", code=status.HTTP_400_BAD_REQUEST
            )

        preview = TaskSyncService.preview_sync(
            work_order, old_process_ids, new_process_ids
        )
        return APIResponse.success(data={"preview": preview})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    @work_order_sync_execute_docs
    def sync_tasks_execute(self, request, pk=None):
        """执行任务同步（需要用户确认）"""
        work_order = self.get_object()
        new_process_ids = request.data.get("process_ids", [])

        if not isinstance(new_process_ids, list):
            return APIResponse.error(
                "process_ids 必须是列表", code=status.HTTP_400_BAD_REQUEST
            )

        old_process_ids = list(
            work_order.order_processes.values_list("id", flat=True)
        )

        if work_order.approval_status == "approved":
            return APIResponse.error(
                "已审核的施工单不能同步任务", code=status.HTTP_400_BAD_REQUEST
            )

        if not request.data.get("confirmed"):
            return APIResponse.error(
                "需要确认后才能执行同步，请设置 confirmed=true",
                code=status.HTTP_400_BAD_REQUEST,
            )

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
        """检查是否需要任务同步"""
        work_order = self.get_object()

        current_process_ids = list(
            work_order.order_processes.values_list("id", flat=True)
        )

        process_ids_str = request.query_params.get("process_ids", "")
        if process_ids_str:
            stored_process_ids = [
                int(pid) for pid in process_ids_str.split(",") if pid.strip()
            ]
        else:
            stored_process_ids = []

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
