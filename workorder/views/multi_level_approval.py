"""
多级审核相关的视图集

包含审核工作流管理、审核步骤处理、紧急订单等功能
"""

import rest_framework.filters
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from workorder.response import APIResponse

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
    MultiLevelApprovalService,
    UrgentOrderService,
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
    def activate(self, request, pk=None):
        """激活工作流"""
        workflow = self.get_object()
        workflow.is_active = True
        workflow.save(update_fields=["is_active"])

        return APIResponse.error("请提供源工作流ID和新名称", code=status.HTTP_400_BAD_REQUEST, data={
                "message": "工作流已激活",
                "workflow": ApprovalWorkflowSerializer(workflow).data,
            }
        )

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """停用工作流"""
        workflow = self.get_object()
        workflow.is_active = False
        workflow.save(update_fields=["is_active"])

        return APIResponse.success(data={
                "message": "工作流已停用",
                "workflow": ApprovalWorkflowSerializer(workflow).data,
            }
        )

    @action(detail=False, methods=["post"])
    def create_default(self, request):
        """创建默认工作流"""
        workflow_types = ["simple", "standard", "complex", "urgent"]
        created_workflows = []

        for workflow_type in workflow_types:
            workflow = MultiLevelApprovalService.create_default_workflow(
                workflow_type, request.user
            )
            created_workflows.append(workflow)

        serializer = ApprovalWorkflowSerializer(created_workflows, many=True)
        return APIResponse.success(
            data={
                "message": f"已创建{len(created_workflows)}个默认工作流",
                "workflows": serializer.data,
            },
            code=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"])
    def duplicate(self, request):
        """复制工作流"""
        source_id = request.data.get("source_id")
        new_name = request.data.get("new_name")

        if not source_id or not new_name:
            return APIResponse.error("请提供源工作流ID和新名称", code=status.HTTP_400_BAD_REQUEST, data={"error": "请提供源工作流ID和新名称"})

        try:
            source_workflow = ApprovalWorkflow.objects.get(id=source_id)

            # 创建副本
            new_workflow = ApprovalWorkflow.objects.create(
                name=new_name,
                workflow_type=source_workflow.workflow_type,
                description=f"复制自 {source_workflow.name}",
                steps=source_workflow.steps,
                is_active=False,  # 默认不激活
                created_by=request.user,
            )

            serializer = ApprovalWorkflowSerializer(new_workflow)
            return APIResponse.success(data={"message": "工作流复制成功", "workflow": serializer.data}, code=status.HTTP_201_CREATED)

        except ApprovalWorkflow.DoesNotExist:
            return APIResponse.error("源工作流不存在", code=status.HTTP_404_NOT_FOUND, data={"error": "源工作流不存在"})


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
    def start_step(self, request, pk=None):
        """开始审核步骤"""
        step = self.get_object()

        if step.status != "pending":
            return APIResponse.error("只能开始待执行的步骤", code=status.HTTP_400_BAD_REQUEST, data={"error": "只能开始待执行的步骤"})

        step.status = "in_progress"
        step.started_at = timezone.now()
        step.save(update_fields=["status", "started_at"])

        return APIResponse.success(
            data={
                "message": "步骤已开始",
                "step": ApprovalStepSerializer(step).data,
            }
        )

    @action(detail=True, methods=["post"])
    def complete_step(self, request, pk=None):
        """完成审核步骤"""
        step = self.get_object()
        serializer = MultiLevelApprovalActionSerializer(data=request.data)

        if not serializer.is_valid():
            return APIResponse.error('请求参数错误', code=status.HTTP_400_BAD_REQUEST, errors=serializer.errors)

        decision = serializer.validated_data["decision"]
        comments = serializer.validated_data.get("comments", "")

        success = MultiLevelApprovalService.complete_approval_step(
            step, decision, comments, request.user
        )

        if success:
            return APIResponse.success(data={
                    "message": "步骤已完成",
                    "decision": decision,
                    "step": ApprovalStepSerializer(step).data,
                }
            )
        else:
            return APIResponse.error("步骤完成失败", code=status.HTTP_400_BAD_REQUEST, data={"error": "步骤完成失败"})

    @action(detail=True, methods=["post"])
    def escalate_step(self, request, pk=None):
        """上报审核步骤"""
        step = self.get_object()
        serializer = EscalationActionSerializer(data=request.data)

        if not serializer.is_valid():
            return APIResponse.error('请求参数错误', code=status.HTTP_400_BAD_REQUEST, errors=serializer.errors)

        escalation_reason = serializer.validated_data["escalation_reason"]
        to_step_id = serializer.validated_data.get("to_step_id")

        # 创建上报记录
        escalation = ApprovalEscalation.objects.create(
            work_order=step.work_order,
            from_step=step,
            to_step_id=to_step_id,
            escalation_reason=escalation_reason,
            escalated_by=request.user,
            status="pending",
        )

        # 更新原步骤状态
        step.status = "completed"
        step.decision = "escalate"
        step.completed_at = timezone.now()
        step.save(update_fields=["status", "decision", "completed_at"])

        return APIResponse.success(
            data={
                "message": "步骤已上报",
                "escalation": ApprovalEscalationSerializer(escalation).data,
            },
            code=status.HTTP_201_CREATED,
        )


class MultiLevelApprovalViewSet(viewsets.GenericViewSet):
    """多级审核主视图集"""

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    def submit_for_approval(self, request):
        """提交施工单进行多级审核"""
        order_id = request.data.get("order_id")

        if not order_id:
            return APIResponse.error("请提供施工单ID", code=status.HTTP_400_BAD_REQUEST, data={"error": "请提供施工单ID"})

        try:
            work_order = WorkOrder.objects.get(id=order_id)

            if work_order.approval_status != "pending":
                return APIResponse.error("只有待审核的订单可以提交审核", code=status.HTTP_400_BAD_REQUEST, data={"error": "只有待审核的订单可以提交审核"})

            # 启动多级审核流程
            approval_steps = MultiLevelApprovalService.start_approval_process(
                work_order, request.user
            )

            return APIResponse.error("施工单不存在", code=status.HTTP_404_NOT_FOUND, data={
                    "message": "审核流程已启动",
                    "approval_steps": ApprovalStepSerializer(
                        approval_steps, many=True).data,
                    "order_number": work_order.order_number,
                    "workflow_type": MultiLevelApprovalService.determine_workflow_type(
                        work_order
                    ),
                }
            )

        except WorkOrder.DoesNotExist:
            return APIResponse.error("施工单不存在", code=status.HTTP_400_BAD_REQUEST, data={"error": "施工单不存在"})

    @action(detail=False, methods=["post"])
    def determine_workflow(self, request):
        """确定施工单的审核工作流类型"""
        serializer = WorkflowDeterminationSerializer(data=request.data)

        if not serializer.is_valid():
            return APIResponse.error('请求参数错误', code=status.HTTP_400_BAD_REQUEST, errors=serializer.errors)

        result = serializer.save()  # save方法会调用to_representation
        return APIResponse.success(data=result)

    @action(detail=False, methods=["get"])
    def get_approval_status(self, request):
        """获取施工单审核状态"""
        serializer = ApprovalStatusSerializer(data=request.data)

        if not serializer.is_valid():
            return APIResponse.error('请求参数错误', code=status.HTTP_400_BAD_REQUEST, errors=serializer.errors)

        result = serializer.save()  # save方法会调用to_representation
        return APIResponse.success(data=result)

    @action(detail=False, methods=["get"])
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
        return APIResponse.error("请提供施工单ID", code=status.HTTP_400_BAD_REQUEST, data={"tasks": serializer.data, "total_count": steps.count()})


class UrgentOrderViewSet(viewsets.GenericViewSet):
    """紧急订单管理视图集"""

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    def mark_urgent(self, request):
        """标记施工单为紧急订单"""
        order_id = request.data.get("order_id")

        if not order_id:
            return APIResponse.error("请提供施工单ID", code=status.HTTP_400_BAD_REQUEST, data={"error": "请提供施工单ID"})

        try:
            work_order = WorkOrder.objects.get(id=order_id)
            serializer = UrgentOrderActionSerializer(data=request.data)

            success = UrgentOrderService.mark_as_urgent(
                work_order, serializer.validated_data.get("reason", ""), request.user
            )

            if success:
                return APIResponse.error("标记失败", code=status.HTTP_400_BAD_REQUEST, data={
                        "message": "订单已标记为紧急",
                        "order_number": work_order.order_number,
                        "urgency_level": UrgentOrderService.calculate_urgency_level(
                            work_order),
                    }
                )
            else:
                return APIResponse.error("标记失败", code=status.HTTP_400_BAD_REQUEST, data={"error": "标记失败"})

        except WorkOrder.DoesNotExist:
            return APIResponse.error("施工单不存在", code=status.HTTP_404_NOT_FOUND, data={"error": "施工单不存在"})

    @action(detail=False, methods=["get"])
    def get_urgent_orders(self, request):
        """获取紧急订单列表"""
        urgent_orders = UrgentOrderService.get_urgent_orders()

        return APIResponse.error("权限不足", code=status.HTTP_403_FORBIDDEN, data={"urgent_orders": urgent_orders, "total_count": len(urgent_orders)}
        )

    @action(detail=False, methods=["get"])
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

    @action(detail=False, methods=["get"])
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
    def dashboard(self, request):
        """管理员仪表板"""
        if not request.user.has_perm("workorder.view_workorder"):
            return APIResponse.error("权限不足", code=status.HTTP_400_BAD_REQUEST, data={"error": "权限不足"})

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
    def smart_assign_task(self, request):
        """智能分配任务"""
        from ..models.core import WorkOrderTask
        from ..services.smart_assignment import SmartAssignmentService

        if not request.user.has_perm("workorder.add_workorder"):
            return APIResponse.error("权限不足", code=status.HTTP_403_FORBIDDEN, data={"error": "权限不足"})

        task_id = request.data.get("task_id")
        if not task_id:
            return APIResponse.error("缺少任务ID", code=status.HTTP_400_BAD_REQUEST, data={"error": "缺少任务ID"})

        try:
            task = WorkOrderTask.objects.get(id=task_id)
        except WorkOrderTask.DoesNotExist:
            return APIResponse.error("任务不存在", code=status.HTTP_404_NOT_FOUND, data={"error": "任务不存在"})

        # 使用智能分配服务
        assignment_service = SmartAssignmentService()
        result = assignment_service.smart_assign_single_task(task)

        if result["success"]:
            return APIResponse.error(result["error"], code=status.HTTP_400_BAD_REQUEST, data={
                    "message": "任务智能分配成功",
                    "task_id": task_id,
                    "assigned_to": result["assigned_to"],
                    "score": result["score"],
                    "reasons": result["reasons"],
                })
        else:
            return APIResponse.error(result["error"], code=status.HTTP_400_BAD_REQUEST, data={"message": "智能分配失败", "error": result["error"]})

    @action(detail=False, methods=["post"])
    def smart_assign_workorder(self, request):
        """智能分配整个施工单的所有任务"""
        from ..models.core import WorkOrder, WorkOrderTask
        from ..services.smart_assignment import SmartAssignmentService

        if not request.user.has_perm("workorder.add_workorder"):
            return APIResponse.error("权限不足", code=status.HTTP_403_FORBIDDEN, data={"error": "权限不足"})

        workorder_id = request.data.get("workorder_id")
        if not workorder_id:
            return APIResponse.error("缺少施工单ID", code=status.HTTP_400_BAD_REQUEST, data={"error": "缺少施工单ID"})

        try:
            workorder = WorkOrder.objects.get(id=workorder_id)
        except WorkOrder.DoesNotExist:
            return APIResponse.error("施工单不存在", code=status.HTTP_404_NOT_FOUND, data={"error": "施工单不存在"})

        # 获取未分配的任务
        unassigned_tasks = WorkOrderTask.objects.filter(
            workorder=workorder, status__in=["pending", "ready"]
        )

        assignment_service = SmartAssignmentService()
        results = []

        for task in unassigned_tasks:
            result = assignment_service.smart_assign_single_task(task)
            results.append(
                {"task_id": task.id, "task_name": task.task_name, "result": result}
            )

        success_count = sum(1 for r in results if r["result"]["success"])

        return APIResponse.error("权限不足", code=status.HTTP_403_FORBIDDEN, data={
                "message": f"智能分配完成，成功分配 {success_count}/{len(results)} 个任务",
                "workorder_id": workorder_id,
                "total_tasks": len(results),
                "success_count": success_count,
                "results": results,
            }
        )

    @action(detail=False, methods=["get"])
    def team_skill_analysis(self, request):
        """团队技能分析"""
        from ..services.smart_assignment import SmartAssignmentService

        if not request.user.has_perm("workorder.view_workorder"):
            return APIResponse.error("权限不足", code=status.HTTP_400_BAD_REQUEST, data={"error": "权限不足"})

        department_id = request.query_params.get("department_id")

        assignment_service = SmartAssignmentService()
        analysis = assignment_service.analyze_team_balance(department_id)

        return APIResponse.success(data=analysis)

    @action(detail=False, methods=["get"])
    def user_performance_summary(self, request):
        """用户绩效统计"""
        from ..services.smart_assignment import SmartAssignmentService

        user_id = request.query_params.get("user_id")
        if not user_id:
            return APIResponse.error("缺少用户ID", code=status.HTTP_400_BAD_REQUEST, data={"error": "缺少用户ID"})

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return APIResponse.error("用户不存在", code=status.HTTP_404_NOT_FOUND, data={"error": "用户不存在"})

        # 权限检查：用户只能查看自己的统计，管理员可以查看所有
        if (
            not request.user.has_perm("workorder.view_workorder")
            and request.user.id != user.id
        ):
            return APIResponse.error("权限不足", code=status.HTTP_403_FORBIDDEN, data={"error": "权限不足"})

        assignment_service = SmartAssignmentService()
        summary = assignment_service.get_user_performance_summary(user)

        return APIResponse.success(data=summary)

    @action(detail=False, methods=["post"])
    def update_skill_profile(self, request):
        """更新用户技能档案"""
        from ..services.smart_assignment import SkillProfile

        user_id = request.data.get("user_id")
        if not user_id:
            return APIResponse.error("缺少用户ID", code=status.HTTP_400_BAD_REQUEST, data={"error": "缺少用户ID"})

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return APIResponse.error("用户不存在", code=status.HTTP_404_NOT_FOUND, data={"error": "用户不存在"})

        # 权限检查：用户只能更新自己的档案，管理员可以更新所有
        if (
            not request.user.has_perm("workorder.change_workorder")
            and request.user.id != user.id
        ):
            return APIResponse.error("权限不足", code=status.HTTP_403_FORBIDDEN, data={"error": "权限不足"})

        skills_data = request.data.get("skills", [])

        skill_profile, created = SkillProfile.objects.get_or_create(user=user)

        # 清除现有技能
        skill_profile.skills.clear()

        # 添加新技能
        for skill_data in skills_data:
            from ..models.core import Process

            process_id = skill_data.get("process_id")
            level = skill_data.get("level", SkillProfile.SKILL_LEVEL_BASIC)

            try:
                process = Process.objects.get(id=process_id)
                skill_profile.skills.add(process, through_defaults={"level": level})
            except Process.DoesNotExist:
                continue

        return APIResponse.success(data={
                "message": "技能档案更新成功",
                "user_id": user_id,
                "skills_count": skill_profile.skills.count(),
            }
        )
