"""施工单流程视图

通过 WorkOrderFlowPolicy 校验权限、WorkOrderFlowService 执行业务，保持视图层仅负责入参/出参。
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from workorder.response import APIResponse

from ..models.core import WorkOrder
from ..policies.work_order_flow_policy import WorkOrderFlowPolicy
from ..services.work_order_flow_service import WorkOrderFlowService
from ..serializers.core import WorkOrderDetailSerializer
from ._decorators import handle_flow_errors


class WorkOrderFlowViewSet(viewsets.GenericViewSet):
    """施工单流程视图集"""

    permission_classes = [IsAuthenticated]
    queryset = WorkOrder.objects.all()
    serializer_class = WorkOrderDetailSerializer

    @staticmethod
    def _build_create_payload(
        request,
        *,
        sales_order_id,
        additional_data: dict,
    ) -> dict:
        return {
            "sales_order_id": sales_order_id,
            "production_quantity": request.data.get("production_quantity"),
            "selected_items": request.data.get("selected_items"),
            "delivery_date": request.data.get("delivery_date"),
            "priority": request.data.get("priority", "normal"),
            "notes": request.data.get("notes", ""),
            "created_by": request.user,
            "additional_data": additional_data,
        }

    # ========== 流程 1: 从客户订单创建施工单 ==========
    @action(detail=False, methods=["post"])
    @handle_flow_errors(message_prefix="创建失败：")
    def create_from_sales_order(self, request):
        """从客户订单创建施工单"""
        WorkOrderFlowPolicy.require_permission(
            request.user,
            "workorder.add_workorder",
            "无权从客户订单创建施工单",
        )
        WorkOrderFlowPolicy.ensure_sales_order_visible(
            sales_order_id=request.data.get("sales_order_id"),
            user=request.user,
        )
        work_order = WorkOrderFlowService.create_from_sales_order(
            **self._build_create_payload(
                request,
                sales_order_id=request.data.get("sales_order_id"),
                additional_data={
                    "artwork_ids": request.data.get("artwork_ids", []),
                    "die_ids": request.data.get("die_ids", []),
                    "foiling_plate_ids": request.data.get(
                        "foiling_plate_ids", []
                    ),
                    "embossing_plate_ids": request.data.get(
                        "embossing_plate_ids", []
                    ),
                },
            )
        )

        response_data = {
            "id": work_order.id,
            "order_number": work_order.order_number,
        }
        asset_link_result = getattr(work_order, "_asset_link_result", None)
        if asset_link_result:
            response_data["asset_link_result"] = asset_link_result

        return APIResponse.success(
            data=response_data,
            message="施工单创建成功",
            code=status.HTTP_201_CREATED,
        )

    # ========== 批量从客户订单创建施工单 ==========
    @action(detail=False, methods=["post"])
    @handle_flow_errors(message_prefix="批量创建失败：")
    def create_from_sales_orders(self, request):
        """批量从客户订单创建施工单"""
        sales_order_ids = request.data.get("sales_order_ids") or []
        if not isinstance(sales_order_ids, list) or len(sales_order_ids) == 0:
            return APIResponse.error(
                message="sales_order_ids 不能为空",
                code=status.HTTP_400_BAD_REQUEST,
            )

        for sales_order_id in sales_order_ids:
            WorkOrderFlowPolicy.ensure_sales_order_visible(
                sales_order_id=sales_order_id,
                user=request.user,
            )

        result = WorkOrderFlowService.create_from_sales_orders_batch(
            sales_order_ids=sales_order_ids,
            request_data=request.data,
            user=request.user,
            allow_partial=request.data.get("allow_partial", False),
        )
        created = result["created"]
        failed = result["failed"]

        message = "批量创建完成"
        if created and not failed:
            message = "批量创建成功"
        elif not created and failed:
            message = "批量创建失败"
        elif created and failed:
            message = f"批量创建部分成功：{len(created)} 个成功，{len(failed)} 个失败"

        return APIResponse.success(
            data={"created": created, "failed": failed},
            message=message,
            code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    # ========== 流程 2: 提交审核 ==========
    @action(detail=True, methods=["post"])
    @handle_flow_errors(message_prefix="提交失败：")
    def submit_approval(self, request, pk=None):
        """提交施工单审核"""
        work_order = self.get_object()
        WorkOrderFlowPolicy.ensure_work_order_writable(
            work_order=work_order,
            user=request.user,
        )

        updated_work_order = WorkOrderFlowService.submit_for_approval(
            work_order_id=work_order.id,
            submitted_by=request.user,
            comment=request.data.get("comment", ""),
            auto_approve=request.data.get("auto_approve", False),
        )

        serializer = WorkOrderDetailSerializer(updated_work_order)
        return APIResponse.success(
            data=serializer.data,
            message="施工单已提交审核",
        )

    # ========== 流程 3: 审核通过（自动化）==========
    @action(detail=True, methods=["post"])
    @handle_flow_errors(message_prefix="审核失败：")
    def approve(self, request, pk=None):
        """审核通过施工单（自动触发任务分派）"""
        work_order = self.get_object()
        WorkOrderFlowPolicy.validate_approval_permissions(
            work_order=work_order,
            user=request.user,
        )

        updated_work_order = WorkOrderFlowService.handle_approval_passed(
            work_order=work_order,
            approved_by=request.user,
            comment=request.data.get("comment", ""),
        )

        serializer = WorkOrderDetailSerializer(updated_work_order)
        data = dict(serializer.data)
        task_generation = getattr(
            updated_work_order, "_task_generation_result", None
        )
        procurement_summary = getattr(
            updated_work_order, "_procurement_summary", None
        )
        if task_generation is not None:
            data["task_generation"] = {
                key: value
                for key, value in task_generation.items()
                if key != "tasks"
            }
        if procurement_summary is not None:
            data["procurement_summary"] = procurement_summary
        return APIResponse.success(
            data=data,
            message="施工单已审核通过，任务已自动分派",
        )

    # ========== 流程 4: 审核拒绝 ==========
    @action(detail=True, methods=["post"])
    @handle_flow_errors(message_prefix="审核失败：")
    def reject(self, request, pk=None):
        """审核拒绝施工单"""
        work_order = self.get_object()
        reason = request.data.get("reason", "")
        WorkOrderFlowPolicy.validate_approval_permissions(
            work_order=work_order,
            user=request.user,
        )

        if not reason:
            return APIResponse.error(
                message="拒绝原因不能为空",
                code=status.HTTP_400_BAD_REQUEST,
            )

        updated_work_order = WorkOrderFlowService.handle_approval_rejected(
            work_order=work_order,
            rejected_by=request.user,
            reason=reason,
        )

        serializer = WorkOrderDetailSerializer(updated_work_order)
        return APIResponse.success(
            data=serializer.data,
            message="施工单已审核拒绝",
        )

    # ========== 工具方法：检查并完成施工单 ==========
    @action(detail=True, methods=["post"])
    @handle_flow_errors(message_prefix="检查失败：")
    def check_completion(self, request, pk=None):
        """检查施工单是否所有任务都已完成，如是则标记为已完成"""
        work_order = self.get_object()
        WorkOrderFlowPolicy.require_permission(
            request.user,
            "workorder.change_workorder",
            "无权检查施工单完成状态",
        )

        is_completed = WorkOrderFlowService.check_and_complete_workorder(
            work_order=work_order
        )

        if is_completed:
            serializer = WorkOrderDetailSerializer(work_order)
            return APIResponse.success(
                data=serializer.data,
                message="所有任务已完成，施工单已标记为完成",
            )
        else:
            return APIResponse.success(
                data={"status": "in_progress"},
                message="施工单仍在进行中",
            )

    # ========== 数据完整性检查 ==========
    @action(detail=True, methods=["get"])
    @handle_flow_errors(message_prefix="检查失败：")
    def check_completeness(self, request, pk=None):
        """检查施工单数据完整性（提交审核前预校验）"""
        work_order = self.get_object()
        errors = work_order.validate_before_approval()
        return APIResponse.success(
            data={
                "is_valid": len(errors) == 0,
                "errors": errors,
            },
            message="验证通过" if not errors else "存在数据不完整项",
        )

    @action(detail=True, methods=["post"])
    @handle_flow_errors(message_prefix="标记失败：")
    def mark_urgent(self, request, pk=None):
        """标记施工单为紧急"""
        work_order = self.get_object()
        updated_work_order = WorkOrderFlowService.mark_urgent(
            work_order=work_order,
            reason=request.data.get("reason", ""),
            user=request.user,
        )
        serializer = WorkOrderDetailSerializer(updated_work_order)
        return APIResponse.success(
            data=serializer.data, message="已标记为紧急施工单"
        )
