"""
施工单流程视图（使用 WorkOrderFlowService）

展示如何在视图中使用流程编排服务，保持视图层简洁
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from workorder.response import APIResponse

from ..services.work_order_flow_service import WorkOrderFlowService
from ..services.work_order_service import WorkOrderService
from ..services.service_errors import ServiceError
from ..serializers.core import WorkOrderDetailSerializer


class WorkOrderFlowViewSet(viewsets.ViewSet):
    """
    施工单流程视图集

    使用 WorkOrderFlowService 编排业务流程
    """

    permission_classes = [IsAuthenticated]

    # ========== 流程 1: 从销售订单创建施工单 ==========
    @action(detail=False, methods=["post"])
    def create_from_sales_order(self, request):
        """
        从销售订单创建施工单

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
        try:
            work_order = WorkOrderFlowService.create_from_sales_order(
                sales_order_id=request.data.get("sales_order_id"),
                production_quantity=request.data.get("production_quantity"),
                delivery_date=request.data.get("delivery_date"),
                priority=request.data.get("priority", "normal"),
                notes=request.data.get("notes", ""),
                created_by=request.user,
                additional_data={
                    "artwork_ids": request.data.get("artwork_ids", []),
                    "die_ids": request.data.get("die_ids", []),
                    "foiling_plate_ids": request.data.get("foiling_plate_ids", []),
                    "embossing_plate_ids": request.data.get("embossing_plate_ids", []),
                },
            )

            return APIResponse.success(
                data={"id": work_order.id, "order_number": work_order.order_number},
                message="施工单创建成功",
                code=status.HTTP_201_CREATED,
            )

        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code)
        except Exception as e:
            return APIResponse.error(message=f"创建失败：{str(e)}", code=500)

    # ========== 流程 2: 提交审核 ==========
    @action(detail=True, methods=["post"])
    def submit_approval(self, request, pk=None):
        """
        提交施工单审核

        请求体：
        {
            "comment": "提交备注"  # 可选
        }
        """
        try:
            work_order = self.get_object()

            updated_work_order = WorkOrderFlowService.submit_for_approval(
                work_order_id=work_order.id,
                submitted_by=request.user,
                comment=request.data.get("comment", ""),
            )

            serializer = WorkOrderDetailSerializer(updated_work_order)
            return APIResponse.success(
                data=serializer.data,
                message="施工单已提交审核",
            )

        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code)
        except Exception as e:
            return APIResponse.error(message=f"提交失败：{str(e)}", code=500)

    # ========== 流程 3: 审核通过（自动化）==========
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """
        审核通过施工单（自动触发任务分派）

        请求体：
        {
            "comment": "审核意见"  # 可选
        }
        """
        try:
            work_order = self.get_object()

            # 调用审核通过流程（自动分派任务）
            updated_work_order = WorkOrderFlowService.handle_approval_passed(
                work_order=work_order,
                approved_by=request.user,
                comment=request.data.get("comment", ""),
            )

            serializer = WorkOrderDetailSerializer(updated_work_order)
            return APIResponse.success(
                data=serializer.data,
                message="施工单已审核通过，任务已自动分派",
            )

        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code)
        except Exception as e:
            return APIResponse.error(message=f"审核失败：{str(e)}", code=500)

    # ========== 流程 4: 审核拒绝 ==========
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """
        审核拒绝施工单

        请求体：
        {
            "reason": "拒绝原因（必填）"
        }
        """
        try:
            work_order = self.get_object()
            reason = request.data.get("reason", "")

            if not reason:
                return APIResponse.error(message="拒绝原因不能为空", code=400)

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

        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code)
        except Exception as e:
            return APIResponse.error(message=f"审核失败：{str(e)}", code=500)

    # ========== 流程 5: 请求重新审核 ==========
    @action(detail=True, methods=["post"])
    def request_reapproval(self, request, pk=None):
        """
        请求重新审核（已审核通过的施工单修改后）

        请求体：
        {
            "reason": "请求原因"  # 可选
        }
        """
        try:
            work_order = self.get_object()

            result = WorkOrderService.request_reapproval(
                work_order=work_order,
                user=request.user,
                reason=request.data.get("reason", ""),
            )

            serializer = WorkOrderDetailSerializer(work_order)
            return APIResponse.success(
                data=serializer.data,
                message="已请求重新审核",
            )

        except ServiceError as e:
            return APIResponse.error(message=str(e), code=e.code)
        except Exception as e:
            return APIResponse.error(message=f"请求失败：{str(e)}", code=500)

    # ========== 工具方法：检查并完成施工单 ==========
    @action(detail=True, methods=["post"])
    def check_completion(self, request, pk=None):
        """
        检查施工单是否所有任务都已完成

        当所有任务完成时，自动将施工单标记为已完成
        """
        try:
            work_order = self.get_object()

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
            return APIResponse.error(message=f"检查失败：{str(e)}", code=500)
