"""
施工单流程视图（使用 WorkOrderFlowService）

展示如何在视图中使用流程编排服务，保持视图层简洁
"""

from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from workorder.response import APIResponse

from ..models.sales import SalesOrder
from ..models.core import WorkOrder
from ..models.system import WorkOrderApprovalLog
from ..permission_utils import PermissionUtils
from ..services.work_order_flow_service import WorkOrderFlowService
from ..services.service_errors import ServiceError
from ..serializers.core import WorkOrderDetailSerializer
from ._decorators import handle_flow_errors


class WorkOrderFlowViewSet(viewsets.GenericViewSet):
    """
    施工单流程视图集

    使用 WorkOrderFlowService 编排业务流程
    """

    permission_classes = [IsAuthenticated]
    queryset = WorkOrder.objects.all()
    serializer_class = WorkOrderDetailSerializer

    @staticmethod
    def _require_permission(user, permission: str, message: str = "权限不足") -> None:
        if user.is_superuser or user.has_perm(permission):
            return
        raise ServiceError(message=message, code=status.HTTP_403_FORBIDDEN)

    @staticmethod
    def _ensure_sales_order_visible(*, sales_order_id, user) -> None:
        if not sales_order_id:
            raise ServiceError("请提供客户订单ID", code=status.HTTP_400_BAD_REQUEST)

        queryset = SalesOrder.objects.filter(id=sales_order_id)
        if user.is_superuser or PermissionUtils.is_finance_user(user):
            visible = queryset.exists()
        else:
            visible = queryset.filter(
                PermissionUtils.build_sales_order_scope_q(user, "")
            ).exists()

        if not visible:
            raise ServiceError(
                "客户订单不存在或无权访问", code=status.HTTP_404_NOT_FOUND
            )

    @staticmethod
    def _ensure_work_order_writable(*, work_order: WorkOrder, user) -> None:
        if user.is_superuser or user.has_perm("workorder.submit_workorder"):
            return
        raise ServiceError("您没有提交审核的权限", code=status.HTTP_403_FORBIDDEN)

    @staticmethod
    def _validate_approval_permissions(*, work_order: WorkOrder, user) -> None:
        if work_order.approval_status != "submitted":
            raise ServiceError(
                '只有待审核的施工单可以审核。如需重新审核，请先使用"请求重新审核"功能。',
                code=status.HTTP_400_BAD_REQUEST,
            )
        
        if not user.is_superuser and not user.has_perm("workorder.approve_workorder"):
            raise ServiceError(
                "您没有审核施工单的权限",
                code=status.HTTP_403_FORBIDDEN,
            )

    def _build_create_payload(
        self,
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
        """
        从客户订单创建施工单

        请求体：
        {
            "sales_order_id": 123,
            "production_quantity": 1000,
            "delivery_date": "2026-03-15",
            "priority": "normal",
            "notes": "备注信息",
            "artwork_ids": [1, 2],  # 可选
            "die_ids": [3],  # 可选
            "foiling_plate_ids": [],  # 可选
            "embossing_plate_ids": []  # 可选
        }
        """
        self._require_permission(
            request.user,
            "workorder.add_workorder",
            "无权从客户订单创建施工单",
        )
        self._ensure_sales_order_visible(
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
                    "foiling_plate_ids": request.data.get("foiling_plate_ids", []),
                    "embossing_plate_ids": request.data.get("embossing_plate_ids", []),
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
    def create_from_sales_orders(self, request):
        """
        批量从客户订单创建施工单

        请求体：
        {
            "sales_order_ids": [1, 2, 3],
            "production_quantity": 1000,  # 可选，所有订单统一使用
            "delivery_date": "2026-03-15",  # 可选
            "priority": "normal",  # 可选
            "notes": "备注信息",  # 可选
            "allow_partial": false  # 可选，是否允许部分成功，默认 false（全部成功才提交）
        }
        """
        sales_order_ids = request.data.get("sales_order_ids") or []
        if not isinstance(sales_order_ids, list) or len(sales_order_ids) == 0:
            return APIResponse.error(
                message="sales_order_ids 不能为空",
                code=status.HTTP_400_BAD_REQUEST,
            )

        allow_partial = request.data.get("allow_partial", False)
        try:
            self._require_permission(
                request.user,
                "workorder.add_workorder",
                "无权从客户订单创建施工单",
            )
            for sales_order_id in sales_order_ids:
                self._ensure_sales_order_visible(
                    sales_order_id=sales_order_id,
                    user=request.user,
                )
        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code)

        created = []
        failed = []

        # 使用事务包装，确保原子性
        with transaction.atomic():
            for sales_order_id in sales_order_ids:
                try:
                    work_order = WorkOrderFlowService.create_from_sales_order(
                        **self._build_create_payload(
                            request,
                            sales_order_id=sales_order_id,
                            additional_data={},
                        )
                    )
                    created.append(
                        {
                            "sales_order_id": sales_order_id,
                            "work_order_id": work_order.id,
                            "order_number": work_order.order_number,
                        }
                    )
                except ServiceError as e:
                    if allow_partial:
                        # 部分成功模式：记录失败但继续
                        failed.append(
                            {
                                "sales_order_id": sales_order_id,
                                "error": str(e),
                            }
                        )
                    else:
                        # 严格模式：任何一个失败则全部回滚
                        transaction.set_rollback(True)
                        return APIResponse.error(
                            message=f"批量创建失败，已回滚所有创建：{str(e)}",
                            code=status.HTTP_400_BAD_REQUEST,
                            data={
                                "created_count": len(created),
                                "failed": {
                                    "sales_order_id": sales_order_id,
                                    "error": str(e),
                                },
                            },
                        )
                except Exception as e:
                    if allow_partial:
                        failed.append(
                            {
                                "sales_order_id": sales_order_id,
                                "error": f"创建失败：{str(e)}",
                            }
                        )
                    else:
                        transaction.set_rollback(True)
                        return APIResponse.error(
                            message=f"批量创建失败，已回滚所有创建：{str(e)}",
                            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            data={
                                "created_count": len(created),
                                "failed": {
                                    "sales_order_id": sales_order_id,
                                    "error": f"创建失败：{str(e)}",
                                },
                            },
                        )

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
        """
        提交施工单审核

        请求体：
        {
            "comment": "提交备注"  # 可选
        }
        """
        work_order = self.get_object()
        self._ensure_work_order_writable(
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
        """
        审核通过施工单（自动触发任务分派）

        请求体：
        {
            "comment": "审核意见"  # 可选
        }
        """
        work_order = self.get_object()
        self._validate_approval_permissions(
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
        task_generation = getattr(updated_work_order, "_task_generation_result", None)
        procurement_summary = getattr(updated_work_order, "_procurement_summary", None)
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
        """
        审核拒绝施工单

        请求体：
        {
            "reason": "拒绝原因（必填）"
        }
        """
        work_order = self.get_object()
        reason = request.data.get("reason", "")
        self._validate_approval_permissions(
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
    def check_completion(self, request, pk=None):
        """
        检查施工单是否所有任务都已完成

        当所有任务完成时，自动将施工单标记为已完成
        """
        try:
            work_order = self.get_object()
            self._require_permission(
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

        except Exception as e:
            return APIResponse.error(
                message=f"检查失败：{str(e)}",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ========== 数据完整性检查 ==========
    @action(detail=True, methods=["get"])
    @handle_flow_errors(message_prefix="检查失败：")
    def check_completeness(self, request, pk=None):
        """
        检查施工单数据完整性（提交审核前预校验）

        返回所有验证错误，如果为空则可以提交审核。
        """
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
    def mark_urgent(self, request, pk=None):
        if not request.user.is_superuser and not request.user.has_perm(
            "workorder.change_workorder"
        ):
            return APIResponse.error(
                message="无权标记紧急施工单",
                code=status.HTTP_403_FORBIDDEN,
            )
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return APIResponse.error(
                message="请输入紧急原因",
                code=status.HTTP_400_BAD_REQUEST,
            )

        work_order = self.get_object()
        work_order.priority = "urgent"
        work_order.urgency_reason = reason
        work_order.save(update_fields=["priority", "urgency_reason"])
        WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            action_type="mark_urgent",
            action_by=request.user,
            comments=reason,
        )
        serializer = WorkOrderDetailSerializer(work_order)
        return APIResponse.success(data=serializer.data, message="已标记为紧急施工单")
