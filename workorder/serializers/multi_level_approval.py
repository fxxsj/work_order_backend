"""
多级审核序列化器

包含审核工作流、审核步骤、审核规则等序列化器
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from ..models.multi_level_approval import (
    ApprovalWorkflow, ApprovalStep, ApprovalRule, 
    ApprovalEscalation, MultiLevelApprovalService, UrgentOrderService
)
from ..models.core import WorkOrder


class ApprovalWorkflowSerializer(serializers.ModelSerializer):
    """审核工作流序列化器"""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = ApprovalWorkflow
        fields = [
            'id', 'name', 'workflow_type', 'description', 'steps', 'is_active',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class ApprovalStepSerializer(serializers.ModelSerializer):
    """审核步骤序列化器"""
    work_order_number = serializers.CharField(source='work_order.order_number', read_only=True)
    workflow_name = serializers.CharField(source='workflow.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True)
    
    class Meta:
        model = ApprovalStep
        fields = [
            'id', 'work_order', 'work_order_number', 'workflow', 'workflow_name',
            'step_name', 'step_order', 'assigned_to', 'assigned_to_name',
            'status', 'decision', 'comments', 'started_at', 'completed_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ApprovalRuleSerializer(serializers.ModelSerializer):
    """审核规则序列化器"""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = ApprovalRule
        fields = [
            'id', 'name', 'rule_type', 'conditions', 'workflow_type', 'is_active',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class ApprovalEscalationSerializer(serializers.ModelSerializer):
    """审核上报序列化器"""
    work_order_number = serializers.CharField(source='work_order.order_number', read_only=True)
    from_step_name = serializers.CharField(source='from_step.step_name', read_only=True)
    to_step_name = serializers.CharField(source='to_step.step_name', read_only=True)
    escalated_by_name = serializers.CharField(source='escalated_by.username', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.username', read_only=True)
    
    class Meta:
        model = ApprovalEscalation
        fields = [
            'id', 'work_order', 'work_order_number', 'from_step', 'from_step_name',
            'to_step', 'to_step_name', 'escalation_reason', 'status',
            'escalated_by', 'escalated_by_name', 'resolved_by', 'resolved_by_name',
            'resolution_comments', 'resolved_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class MultiLevelApprovalActionSerializer(serializers.Serializer):
    """多级审核操作序列化器"""
    decision = serializers.ChoiceField(choices=ApprovalStep.DECISION_CHOICES)
    comments = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class EscalationActionSerializer(serializers.Serializer):
    """上报操作序列化器"""
    escalation_reason = serializers.CharField(max_length=500)
    to_step_id = serializers.IntegerField(required=False, allow_null=True)


class UrgentOrderActionSerializer(serializers.Serializer):
    """紧急订单操作序列化器"""
    reason = serializers.CharField(max_length=500)


class WorkflowDeterminationSerializer(serializers.Serializer):
    """工作流确定序列化器"""
    order_id = serializers.IntegerField()
    
    def to_representation(self, instance):
        """自定义响应格式"""
        work_order = WorkOrder.objects.get(id=self.validated_data['order_id'])
        workflow_type = MultiLevelApprovalService.determine_workflow_type(work_order)
        
        return {
            'order_id': work_order.id,
            'order_number': work_order.order_number,
            'workflow_type': workflow_type,
            'workflow_type_display': dict(ApprovalWorkflow.WORKFLOW_TYPES).get(workflow_type),
            'total_amount': work_order.total_amount,
            'priority': work_order.priority,
            'determination_reason': self._get_determination_reason(work_order, workflow_type)
        }
    
    def _get_determination_reason(self, work_order, workflow_type):
        """获取确定原因"""
        reasons = []
        
        if work_order.priority == 'urgent':
            reasons.append('紧急优先级')
        
        if work_order.total_amount >= 50000:
            reasons.append('高价值订单')
        elif work_order.total_amount >= 10000:
            reasons.append('中等价值订单')
        
        if workflow_type == 'simple':
            reasons.append('简单审核流程')
        elif workflow_type == 'standard':
            reasons.append('标准审核流程')
        elif workflow_type == 'complex':
            reasons.append('复杂审核流程')
        elif workflow_type == 'urgent':
            reasons.append('紧急审核流程')
        
        return '、'.join(reasons) if reasons else '默认流程'


class ApprovalStatusSerializer(serializers.Serializer):
    """审核状态序列化器"""
    order_id = serializers.IntegerField()
    
    def to_representation(self, instance):
        """自定义响应格式"""
        work_order = WorkOrder.objects.get(id=self.validated_data['order_id'])
        
        # 获取审核步骤
        steps = ApprovalStep.objects.filter(work_order=work_order).order_by('step_order')
        
        # 获取当前活跃步骤
        current_step = steps.filter(status__in=['pending', 'in_progress']).first()
        
        # 获取最新上报
        latest_escalation = ApprovalEscalation.objects.filter(
            work_order=work_order
        ).order_by('-created_at').first()
        
        return {
            'order_id': work_order.id,
            'order_number': work_order.order_number,
            'approval_status': work_order.approval_status,
            'current_step': ApprovalStepSerializer(current_step).data if current_step else None,
            'all_steps': ApprovalStepSerializer(steps, many=True).data,
            'total_steps': steps.count(),
            'completed_steps': steps.filter(status='completed').count(),
            'progress_percentage': (steps.filter(status='completed').count() / steps.count() * 100) if steps.count() > 0 else 0,
            'latest_escalation': ApprovalEscalationSerializer(latest_escalation).data if latest_escalation else None,
            'urgency_level': UrgentOrderService.calculate_urgency_level(work_order) if work_order.priority == 'urgent' else 0,
            'estimated_completion_time': self._estimate_completion_time(work_order, steps)
        }
    
    def _estimate_completion_time(self, work_order, steps):
        """估算完成时间"""
        if not steps or steps.filter(status='completed').count() == steps.count():
            return None
        
        # 简单估算：每个步骤平均需要1天
        remaining_steps = steps.filter(status__in=['pending', 'in_progress']).count()
        
        from django.utils import timezone
        from datetime import timedelta
        
        return timezone.now() + timedelta(days=remaining_steps)


class SkillProfileSerializer(serializers.Serializer):
    """技能档案序列化器"""
    user_id = serializers.IntegerField()
    skills = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )


class SmartAssignmentResultSerializer(serializers.Serializer):
    """智能分配结果序列化器"""
    success = serializers.BooleanField()
    task_id = serializers.IntegerField(required=False)
    assigned_to = serializers.IntegerField(required=False)
    score = serializers.FloatField(required=False)
    reasons = serializers.ListField(child=serializers.CharField(), required=False)
    error = serializers.CharField(required=False, allow_blank=True)


class TeamAnalysisSerializer(serializers.Serializer):
    """团队分析序列化器"""
    department_id = serializers.IntegerField(required=False, allow_null=True)


class UserPerformanceSerializer(serializers.Serializer):
    """用户绩效序列化器"""
    user_id = serializers.IntegerField()