"""
多级审核相关的视图集

包含审核工作流管理、审核步骤处理、紧急订单等功能
"""

import rest_framework.filters
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets, serializers
from rest_framework.decorators import action
from workorder.response import APIResponse
from workorder.services.approval_actions import (
    activate_workflow,
    complete_step,
    create_default_workflows,
    deactivate_workflow,
    duplicate_workflow,
    escalate_step,
    get_urgent_orders,
    mark_urgent,
    smart_assign_task,
    smart_assign_workorder,
    start_step,
    submit_for_approval,
)
from workorder.services.service_errors import ServiceError
from workorder.policies.approval_policy import require_permission
from workorder.docs.multi_level_approval import (
    approval_report_dashboard_docs,
    approval_report_stats_docs,
    approval_step_complete_docs,
    approval_step_docs,
    approval_step_escalate_docs,
    approval_step_start_docs,
    approval_workflow_activate_docs,
    approval_workflow_create_default_docs,
    approval_workflow_deactivate_docs,
    approval_workflow_docs,
    approval_workflow_duplicate_docs,
    escalation_history_docs,
    multi_level_determine_docs,
    multi_level_my_tasks_docs,
    multi_level_status_docs,
    multi_level_submit_docs,
    smart_assign_task_docs,
    smart_assign_workorder_docs,
    team_skill_analysis_docs,
    urgent_list_docs,
    urgent_mark_docs,
    update_skill_profile_docs,
    user_performance_summary_docs,
)


class EmptySerializer(serializers.Serializer):
    """用于 OpenAPI 生成的空序列化器"""

    pass

from ..models.assets import (
    Artwork,
    ArtworkProduct,
    Die,
    DieProduct,
    EmbossingPlate,
    EmbossingPlateProduct,
    FoilingPlate,
    FoilingPlateProduct,
)
from ..models.base import Customer, Department, Process
from ..models.core import (
    ProcessLog,
    TaskLog,
    WorkOrder,
    WorkOrderMaterial,
    WorkOrderProcess,
    WorkOrderProduct,
    WorkOrderTask,
)
from ..models.materials import Material
from ..models.multi_level_approval import (
    ApprovalEscalation,
    ApprovalRule,
    ApprovalStep,
    ApprovalWorkflow,
)
from ..models.products import Product, ProductMaterial
from ..models.system import UserProfile, WorkOrderApprovalLog
from ..permissions import SuperuserFriendlyModelPermissions
from ..serializers.multi_level_approval import (
    ApprovalEscalationSerializer,
    ApprovalRuleSerializer,
    ApprovalStatusSerializer,
    ApprovalStepSerializer,
    ApprovalWorkflowSerializer,
    EscalationActionSerializer,
    MultiLevelApprovalActionSerializer,
    UrgentOrderActionSerializer,
    WorkflowDeterminationSerializer,
)


@approval_workflow_docs
class ApprovalWorkflowViewSet(viewsets.ModelViewSet):
    """审核工作流管理视图集"""

    queryset = ApprovalWorkflow.objects.all()
    serializer_class = ApprovalWorkflowSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [
        rest_framework.filters.SearchFilter,
        rest_framework.filters.OrderingFilter,
    ]
    search_fields = ["name", "workflow_type", "description"]
    ordering_fields = ["created_at", "updated_at", "workflow_type"]
    ordering = ["-created_at"]

    @action(detail=True, methods=["post"])
    @approval_workflow_activate_docs
    def activate(self, request, pk=None):
        """激活工作流"""
        workflow = activate_workflow(self.get_object())
        serializer = ApprovalWorkflowSerializer(workflow)
        return APIResponse.success(
            data={"workflow": serializer.data},
            message="工作流已激活",
        )

    @action(detail=True, methods=["post"])
    @approval_workflow_deactivate_docs
    def deactivate(self, request, pk=None):
        """停用工作流"""
        workflow = deactivate_workflow(self.get_object())
        serializer = ApprovalWorkflowSerializer(workflow)
        return APIResponse.success(
            data={"workflow": serializer.data},
            message="工作流已停用",
        )

    @action(detail=False, methods=["post"])
    @approval_workflow_create_default_docs
    def create_default(self, request):
        """创建默认工作流"""
        created_workflows = create_default_workflows(request.user)
        serializer = ApprovalWorkflowSerializer(created_workflows, many=True)
        return APIResponse.success(
            data={"workflows": serializer.data},
            message=f"已创建{len(created_workflows)}个默认工作流",
            code=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"])
    @approval_workflow_duplicate_docs
    def duplicate(self, request):
        """复制工作流"""
        source_id = request.data.get("source_id")
        new_name = request.data.get("new_name")

        try:
            new_workflow = duplicate_workflow(
                source_id=source_id, new_name=new_name, user=request.user
            )
            serializer = ApprovalWorkflowSerializer(new_workflow)
            return APIResponse.success(
                data={"workflow": serializer.data},
                message="工作流复制成功",
                code=status.HTTP_201_CREATED,
            )
        except ServiceError as exc:
            return APIResponse.error(
                exc.message, code=exc.code, data=exc.data
            )


@approval_step_docs
class ApprovalStepViewSet(viewsets.ModelViewSet):
    """审核步骤管理视图集"""

    queryset = ApprovalStep.objects.all()
    serializer_class = ApprovalStepSerializer
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [
        rest_framework.filters.SearchFilter,
        rest_framework.filters.OrderingFilter,
    ]
    search_fields = ["step_name", "comments"]
    ordering_fields = ["created_at", "step_order", "status"]
    ordering = ["work_order", "step_order"]

    def get_queryset(self):
        """根据用户权限过滤查询集"""
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        # 普通用户只能看到分配给自己的步骤
        return queryset.filter(Q(assigned_to=user) | Q(work_order__created_by=user))

    @action(detail=True, methods=["post"])
    @approval_step_start_docs
    def start_step(self, request, pk=None):
        """开始审核步骤"""
        try:
            step = start_step(self.get_object())
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        return APIResponse.success(
            data={"step": ApprovalStepSerializer(step).data},
            message="步骤已开始",
        )

    @action(detail=True, methods=["post"])
    @approval_step_complete_docs
    def complete_step(self, request, pk=None):
        """完成审核步骤"""
        step = self.get_object()
        serializer = MultiLevelApprovalActionSerializer(data=request.data)

        if not serializer.is_valid():
            return APIResponse.error('请求参数错误', code=status.HTTP_400_BAD_REQUEST, errors=serializer.errors)

        decision = serializer.validated_data["decision"]
        comments = serializer.validated_data.get("comments", "")

        try:
            complete_step(step, decision, comments, request.user)
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        return APIResponse.success(
            data={
                "decision": decision,
                "step": ApprovalStepSerializer(step).data,
            },
            message="步骤已完成",
        )

    @action(detail=True, methods=["post"])
    @approval_step_escalate_docs
    def escalate_step(self, request, pk=None):
        """上报审核步骤"""
        step = self.get_object()
        serializer = EscalationActionSerializer(data=request.data)

        if not serializer.is_valid():
            return APIResponse.error('请求参数错误', code=status.HTTP_400_BAD_REQUEST, errors=serializer.errors)

        escalation_reason = serializer.validated_data["escalation_reason"]
        to_step_id = serializer.validated_data.get("to_step_id")
        escalation = escalate_step(
            step=step,
            escalation_reason=escalation_reason,
            to_step_id=to_step_id,
            user=request.user,
        )

        return APIResponse.success(
            data={"escalation": ApprovalEscalationSerializer(escalation).data},
            message="步骤已上报",
            code=status.HTTP_201_CREATED,
        )


class MultiLevelApprovalViewSet(viewsets.GenericViewSet):
    """多级审核主视图集"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmptySerializer

    @action(detail=False, methods=["post"])
    @multi_level_submit_docs
    def submit_for_approval(self, request):
        """提交施工单进行多级审核"""
        order_id = request.data.get("order_id")

        try:
            work_order, approval_steps, workflow_type = submit_for_approval(
                order_id=order_id, user=request.user
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        return APIResponse.success(
            data={
                "approval_steps": ApprovalStepSerializer(approval_steps, many=True).data,
                "order_number": work_order.order_number,
                "workflow_type": workflow_type,
            },
            message="审核流程已启动",
        )

    @action(detail=False, methods=["post"])
    @multi_level_determine_docs
    def determine_workflow(self, request):
        """确定施工单的审核工作流类型"""
        serializer = WorkflowDeterminationSerializer(data=request.data)

        if not serializer.is_valid():
            return APIResponse.error('请求参数错误', code=status.HTTP_400_BAD_REQUEST, errors=serializer.errors)

        result = serializer.save()  # save方法会调用to_representation
        return APIResponse.success(data=result)

    @action(detail=False, methods=["get"])
    @multi_level_status_docs
    def get_approval_status(self, request):
        """获取施工单审核状态"""
        serializer = ApprovalStatusSerializer(data=request.data)

        if not serializer.is_valid():
            return APIResponse.error('请求参数错误', code=status.HTTP_400_BAD_REQUEST, errors=serializer.errors)

        result = serializer.save()  # save方法会调用to_representation
        return APIResponse.success(data=result)

    @action(detail=False, methods=["get"])
    @multi_level_my_tasks_docs
    def get_my_tasks(self, request):
        """获取当前用户的审核任务"""
        user = request.user

        # 获取分配给用户的待执行和执行中的步骤
        steps = (
            ApprovalStep.objects.filter(
                assigned_to=user, status__in=["pending", "in_progress"]
            )
            .select_related("work_order", "work_order__customer", "workflow")
            .order_by("created_at")
        )

        serializer = ApprovalStepSerializer(steps, many=True)
        return APIResponse.success(
            data={"tasks": serializer.data, "total_count": steps.count()}
        )


class UrgentOrderViewSet(viewsets.GenericViewSet):
    """紧急订单管理视图集"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmptySerializer

    @action(detail=False, methods=["post"])
    @urgent_mark_docs
    def mark_urgent(self, request):
        """标记施工单为紧急订单"""
        order_id = request.data.get("order_id")

        serializer = UrgentOrderActionSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                "请求参数错误",
                code=status.HTTP_400_BAD_REQUEST,
                errors=serializer.errors,
            )

        try:
            work_order, urgency_level = mark_urgent(
                order_id=order_id,
                reason=serializer.validated_data.get("reason", ""),
                user=request.user,
            )
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        return APIResponse.success(
            data={
                "order_number": work_order.order_number,
                "urgency_level": urgency_level,
            },
            message="订单已标记为紧急",
        )

    @action(detail=False, methods=["get"])
    @urgent_list_docs
    def get_urgent_orders(self, request):
        """获取紧急订单列表"""
        try:
            require_permission(request.user, "workorder.view_workorder")
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        urgent_orders = get_urgent_orders()
        return APIResponse.success(
            data={"urgent_orders": urgent_orders, "total_count": len(urgent_orders)}
        )

    @action(detail=False, methods=["get"])
    @escalation_history_docs
    def get_escalation_history(self, request):
        """获取上报历史记录"""
        user = request.user

        escalations = (
            ApprovalEscalation.objects.filter(escalated_by=user)
            .select_related("work_order", "from_step", "to_step", "resolved_by")
            .order_by("-created_at")[:50]
        )  # 最近50条

        serializer = ApprovalEscalationSerializer(escalations, many=True)
        return APIResponse.success(data={"escalations": serializer.data, "total_count": escalations.count()}
        )


class ApprovalReportViewSet(viewsets.GenericViewSet):
    """审核报告视图集"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmptySerializer

    @action(detail=False, methods=["get"])
    @approval_report_stats_docs
    def get_statistics(self, request):
        """获取审核统计报告"""
        from datetime import timedelta

        from django.db.models import Count, Q
        from django.utils import timezone

        # 基础统计
        total_orders = WorkOrder.objects.count()
        pending_orders = WorkOrder.objects.filter(approval_status="pending").count()
        approved_orders = WorkOrder.objects.filter(approval_status="approved").count()
        rejected_orders = WorkOrder.objects.filter(approval_status="rejected").count()

        # 近30天统计
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_orders = WorkOrder.objects.filter(
            created_at__gte=thirty_days_ago
        ).count()
        recent_approved = WorkOrder.objects.filter(
            created_at__gte=thirty_days_ago, approval_status="approved"
        ).count()

        # 工作流统计
        workflow_stats = (
            ApprovalWorkflow.objects.values("workflow_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # 紧急订单统计
        urgent_orders = WorkOrder.objects.filter(priority="urgent").count()
        urgent_pending = WorkOrder.objects.filter(
            priority="urgent", approval_status="pending"
        ).count()

        return APIResponse.success(data={
                "overall": {
                    "total_orders": total_orders,
                    "pending_orders": pending_orders,
                    "approved_orders": approved_orders,
                    "rejected_orders": rejected_orders,
                    "approval_rate": (
                        round(approved_orders / total_orders * 100, 2)
                        if total_orders > 0
                        else 0
                    ),
                },
                "recent_thirty_days": {
                    "total_orders": recent_orders,
                    "approved_orders": recent_approved,
                    "approval_rate": (
                        round(recent_approved / recent_orders * 100, 2)
                        if recent_orders > 0
                        else 0
                    ),
                },
                "workflow_distribution": list(workflow_stats),
                "urgent_orders": {
                    "total_urgent": urgent_orders,
                    "pending_urgent": urgent_pending,
                    "urgent_percentage": (
                        round(urgent_orders / total_orders * 100, 2)
                        if total_orders > 0
                        else 0
                    ),
                },
            }
        )

    @action(detail=False, methods=["get"])
    @approval_report_dashboard_docs
    def dashboard(self, request):
        """管理员仪表板"""
        try:
            require_permission(request.user, "workorder.view_workorder", code=403)
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        dashboard_data = {
            "pending_orders": ApprovalStep.objects.filter(status="pending").count(),
            "in_review_orders": ApprovalStep.objects.filter(
                status="in_progress"
            ).count(),
            "urgent_orders": WorkOrder.objects.filter(
                priority="urgent", approval_status__in=["pending", "in_review"]
            ).count(),
            "completed_today": ApprovalStep.objects.filter(
                status="completed", completed_at__date=timezone.now().date()
            ).count(),
        }

        return APIResponse.success(data=dashboard_data)

    @action(detail=False, methods=["post"])
    @smart_assign_task_docs
    def smart_assign_task(self, request):
        """智能分配任务"""
        from ..models.core import WorkOrderTask

        try:
            require_permission(request.user, "workorder.add_workorder", code=403)
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        task_id = request.data.get("task_id")
        if not task_id:
            return APIResponse.error("缺少任务ID", code=status.HTTP_400_BAD_REQUEST)

        try:
            task = WorkOrderTask.objects.get(id=task_id)
        except WorkOrderTask.DoesNotExist:
            return APIResponse.error("任务不存在", code=status.HTTP_404_NOT_FOUND)

        result = smart_assign_task(task)

        if result["success"]:
            return APIResponse.success(
                data={
                    "task_id": task_id,
                    "assigned_to": result["assigned_to"],
                    "score": result["score"],
                    "reasons": result["reasons"],
                },
                message="任务智能分配成功",
            )
        return APIResponse.error(result["error"], code=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    @smart_assign_workorder_docs
    def smart_assign_workorder(self, request):
        """智能分配整个施工单的所有任务"""
        from ..models.core import WorkOrder

        try:
            require_permission(request.user, "workorder.add_workorder", code=403)
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        workorder_id = request.data.get("workorder_id")
        if not workorder_id:
            return APIResponse.error("缺少施工单ID", code=status.HTTP_400_BAD_REQUEST)

        try:
            workorder = WorkOrder.objects.get(id=workorder_id)
        except WorkOrder.DoesNotExist:
            return APIResponse.error("施工单不存在", code=status.HTTP_404_NOT_FOUND)

        results, success_count = smart_assign_workorder(workorder)
        return APIResponse.success(
            data={
                "workorder_id": workorder_id,
                "total_tasks": len(results),
                "success_count": success_count,
                "results": results,
            },
            message=f"智能分配完成，成功分配 {success_count}/{len(results)} 个任务",
        )

    @action(detail=False, methods=["get"])
    @team_skill_analysis_docs
    def team_skill_analysis(self, request):
        """团队技能分析"""
        from ..services.smart_assignment import SmartAssignmentService

        try:
            require_permission(request.user, "workorder.view_workorder", code=403)
        except ServiceError as exc:
            return APIResponse.error(exc.message, code=exc.code, data=exc.data)

        department_id = request.query_params.get("department_id")

        assignment_service = SmartAssignmentService()
        analysis = assignment_service.analyze_team_balance(department_id)

        return APIResponse.success(data=analysis)

    @action(detail=False, methods=["get"])
    @user_performance_summary_docs
    def user_performance_summary(self, request):
        """用户绩效统计"""
        from ..services.smart_assignment import SmartAssignmentService

        user_id = request.query_params.get("user_id")
        if not user_id:
            return APIResponse.error("缺少用户ID", code=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return APIResponse.error("用户不存在", code=status.HTTP_404_NOT_FOUND)

        # 权限检查：用户只能查看自己的统计，管理员可以查看所有
        if (
            not request.user.has_perm("workorder.view_workorder")
            and request.user.id != user.id
        ):
            return APIResponse.error("权限不足", code=status.HTTP_403_FORBIDDEN)

        assignment_service = SmartAssignmentService()
        summary = assignment_service.get_user_performance_summary(user)

        return APIResponse.success(data=summary)

    @action(detail=False, methods=["post"])
    @update_skill_profile_docs
    def update_skill_profile(self, request):
        """更新用户技能档案"""
        return APIResponse.error("技能画像已禁用", code=status.HTTP_501_NOT_IMPLEMENTED)
