"""
施工单任务操作 Mixin

包含单个任务的操作方法。
"""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import action
from workorder.response import APIResponse
from workorder.schema import standard_error_response, standard_success_response
from workorder.services.service_errors import ServiceError
from workorder.policies.task_policy import (
    ensure_assets_confirmed,
    ensure_material_cut_ready,
    ensure_task_version,
    ensure_user_can_modify_task,
)

from workorder.serializers.core import TaskAssignmentSerializer, WorkOrderTaskSerializer
from workorder.services.task_assignment import TaskAssignmentService
from workorder.services.task_action_service import TaskActionService


class TaskActionsMixin:
    """
    任务操作 Mixin

    提供单个任务的操作方法，包括更新数量、完成任务、拆分任务等。
    """

    @extend_schema(
        tags=["任务"],
        summary="更新任务完成数量",
        description="""
        操作员更新任务的完成数量（增量更新）。

        **业务规则**:
        - 操作员只能更新自己分派的任务
        - 更新数量为增量（本次完成数量）
        - 完成数量不能超过生产数量
        - 根据完成数量自动更新任务状态
        - 使用版本号进行并发控制

        **并发控制**: 乐观锁，检测版本号冲突
        """,
        request=inline_serializer(
            name="TaskUpdateQuantityRequest",
            fields={
                "quantity_increment": serializers.IntegerField(
                    help_text="本次完成数量"
                ),
                "quantity_defective": serializers.IntegerField(
                    required=False, default=0, help_text="次品数量"
                ),
                "notes": serializers.CharField(
                    required=False, allow_blank=True, help_text="备注信息"
                ),
                "version": serializers.IntegerField(
                    required=False, help_text="版本号（并发控制）"
                ),
            },
        ),
        examples=[
            OpenApiExample(
                name="示例请求",
                summary="增量更新完成数量",
                value={
                    "quantity_increment": 50,
                    "quantity_defective": 2,
                    "notes": "本次印刷有少量破损",
                    "version": 3,
                },
                request_only=True,
            )
        ],
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "TaskUpdateQuantityResponse", WorkOrderTaskSerializer
                ),
                description="更新成功",
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="更新成功返回",
                        value={
                            "success": True,
                            "code": 200,
                            "message": "操作成功",
                            "data": {
                                "id": 101,
                                "status": "in_progress",
                                "status_display": "进行中",
                                "quantity_completed": 170,
                                "quantity_defective": 2,
                                "updated_at": "2026-03-02T10:20:00+08:00",
                            },
                            "timestamp": "2026-03-02T10:20:00+08:00",
                        },
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(
                response=standard_error_response("TaskUpdateQuantityBadRequest"),
                description="请求无效或业务规则验证失败",
            ),
            403: OpenApiResponse(
                response=standard_error_response("TaskUpdateQuantityForbidden"),
                description="权限不足",
            ),
            409: OpenApiResponse(
                response=standard_error_response("TaskUpdateQuantityConflict"),
                description="并发冲突",
            ),
        },
    )
    @action(detail=True, methods=["post"])
    def update_quantity(self, request, pk=None):
        """更新任务数量（包含业务条件验证，根据数量自动判断状态，记录操作人）"""
        task = self.get_object()

        try:
            ensure_user_can_modify_task(request.user, task, "更新")
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        expected_version = request.data.get("version")
        try:
            ensure_task_version(task, expected_version)
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        try:
            TaskActionService.update_quantity(
                task=task,
                quantity_increment=request.data.get("quantity_increment"),
                quantity_defective=request.data.get("quantity_defective", 0),
                notes=request.data.get("notes", ""),
                work_hours=request.data.get("work_hours"),
                machine_name=request.data.get("machine_name", ""),
                operator_count=request.data.get("operator_count"),
                user=request.user,
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)
        except Exception as exc:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"更新任务数量失败: {str(exc)}")
            return APIResponse.error(
                "更新任务数量失败，请稍后重试",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = self.get_serializer(task)
        return APIResponse.success(data=serializer.data)

    @extend_schema(
        tags=["任务"],
        summary="强制完成任务",
        description="""
        操作员标记任务为完成状态（即使完成数量小于生产数量）。

        **业务规则**:
        - 操作员只能完成自己分派的任务
        - 可记录次品数量
        - 可填写完成原因和备注
        - 任务状态变更为 completed
        - 发送任务完成通知

        **并发控制**: 乐观锁，检测版本号冲突
        """,
        request=inline_serializer(
            name="TaskCompleteRequest",
            fields={
                "completion_reason": serializers.CharField(
                    required=False, allow_blank=True, help_text="完成原因"
                ),
                "quantity_defective": serializers.IntegerField(
                    required=False, default=0, help_text="次品数量"
                ),
                "notes": serializers.CharField(
                    required=False, allow_blank=True, help_text="备注信息"
                ),
                "version": serializers.IntegerField(
                    required=False, help_text="版本号（并发控制）"
                ),
            },
        ),
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "TaskCompleteResponse", WorkOrderTaskSerializer
                ),
                description="完成成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("TaskCompleteBadRequest"),
                description="请求无效或业务规则验证失败",
            ),
            403: OpenApiResponse(
                response=standard_error_response("TaskCompleteForbidden"),
                description="权限不足",
            ),
            409: OpenApiResponse(
                response=standard_error_response("TaskCompleteConflict"),
                description="并发冲突",
            ),
        },
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """强制完成任务（用于完成数量小于生产数量但需要强制标志为已完成的情况）"""
        task = self.get_object()

        try:
            ensure_user_can_modify_task(request.user, task, "完成")
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        expected_version = request.data.get("version")
        try:
            ensure_task_version(task, expected_version)
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        try:
            TaskActionService.complete_task(
                task=task,
                completion_reason=request.data.get("completion_reason", ""),
                quantity_defective=request.data.get("quantity_defective", 0),
                notes=request.data.get("notes", ""),
                user=request.user,
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)
        except Exception as exc:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"强制完成任务失败: {str(exc)}")
            return APIResponse.error(
                "强制完成任务失败，请稍后重试",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = self.get_serializer(task)
        return APIResponse.success(data=serializer.data)

    @action(detail=True, methods=["post"])
    def split(self, request, pk=None):
        """拆分任务为多个子任务（支持多人协作）"""
        task = self.get_object()

        try:
            result = TaskActionService.split_task(
                task=task,
                splits=request.data.get("splits", []),
                user=request.user,
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)
        except Exception as exc:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"任务拆分失败: {str(exc)}")
            return APIResponse.error(
                "任务拆分失败，请稍后重试",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = self.get_serializer(result["parent_task"])
        return APIResponse.success(
            data={
                "message": f"任务已成功拆分为{len(result['created_subtasks'])}个子任务",
                "parent_task": serializer.data,
                "subtasks_count": len(result["created_subtasks"]),
            },
            code=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """分派任务给部门或操作员"""
        task = self.get_object()
        serializer = TaskAssignmentSerializer(data=request.data)

        if not serializer.is_valid():
            return APIResponse.error(
                "请求参数错误",
                code=status.HTTP_400_BAD_REQUEST,
                errors=serializer.errors,
            )

        try:
            result = TaskActionService.assign_task(
                task=task,
                assigned_department=serializer.validated_data.get("assigned_department"),
                assigned_operator=serializer.validated_data.get("assigned_operator"),
                notes=serializer.validated_data.get("notes", ""),
                reason=serializer.validated_data.get("reason", ""),
                user=request.user,
            )

            task.refresh_from_db()
            response_serializer = self.get_serializer(task)
            return APIResponse.success(
                data={
                    "detail": "任务分配成功",
                    "data": result["operator_assignment_result"],
                    "task": response_serializer.data,
                },
                code=status.HTTP_200_OK,
            )
        except ServiceError as exc:
            retry_info = TaskAssignmentService.get_retry_suggestion(exc)
            error_response = {
                "detail": exc.message,
                "code": "error",
                "retry": retry_info,
            }
            if exc.data:
                error_response.update(exc.data)
            return APIResponse.error(
                exc.message,
                code=exc.code,
                data=error_response,
            )
        except Exception as exc:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"任务分配失败: {str(exc)}")
            return APIResponse.error(
                "任务分配失败，请稍后重试",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """取消任务"""
        task = self.get_object()
        cancellation_reason = request.data.get("cancellation_reason", "").strip()
        notes = request.data.get("notes", "")

        try:
            TaskActionService.cancel_task(
                task=task,
                cancellation_reason=cancellation_reason,
                notes=notes,
                user=request.user,
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)
        except Exception as exc:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"取消任务失败: {str(exc)}")
            return APIResponse.error(
                "取消任务失败，请稍后重试",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = self.get_serializer(task)
        return APIResponse.success(
            data={"task": serializer.data}, message="任务已成功取消"
        )
