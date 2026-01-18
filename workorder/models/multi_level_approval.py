"""
多级审核模型

包含审核工作流、审核步骤、审核规则等模型定义
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import json


class ApprovalWorkflow(models.Model):
    """审核工作流模板"""
    
    WORKFLOW_TYPES = [
        ('simple', '简单审核'),
        ('standard', '标准审核'),
        ('complex', '复杂审核'),
        ('urgent', '紧急审核'),
    ]
    
    name = models.CharField('工作流名称', max_length=100)
    workflow_type = models.CharField('工作流类型', max_length=20, choices=WORKFLOW_TYPES)
    description = models.TextField('描述', blank=True)
    steps = models.JSONField('审核步骤配置', default=dict)
    is_active = models.BooleanField('是否激活', default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        db_table = 'approval_workflow'
        verbose_name = '审核工作流'
        verbose_name_plural = '审核工作流'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_workflow_type_display()})"


class ApprovalStep(models.Model):
    """审核步骤"""
    
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('in_progress', '审核中'),
        ('completed', '已完成'),
        ('skipped', '已跳过'),
    ]
    
    DECISION_CHOICES = [
        ('approve', '通过'),
        ('reject', '拒绝'),
        ('escalate', '上报'),
    ]
    
    work_order = models.ForeignKey(
        'WorkOrder', 
        on_delete=models.CASCADE, 
        verbose_name='施工单',
        related_name='approval_steps'
    )
    workflow = models.ForeignKey(
        ApprovalWorkflow, 
        on_delete=models.CASCADE, 
        verbose_name='工作流'
    )
    step_name = models.CharField('步骤名称', max_length=100)
    step_order = models.IntegerField('步骤顺序')
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='分配给',
        related_name='assigned_approval_steps'
    )
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    decision = models.CharField('审核决定', max_length=20, choices=DECISION_CHOICES, blank=True)
    comments = models.TextField('审核意见', blank=True)
    started_at = models.DateTimeField('开始时间', null=True, blank=True)
    completed_at = models.DateTimeField('完成时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        db_table = 'approval_step'
        verbose_name = '审核步骤'
        verbose_name_plural = '审核步骤'
        ordering = ['work_order', 'step_order']
        unique_together = ['work_order', 'step_order']
    
    def __str__(self):
        return f"{self.work_order.order_number} - {self.step_name}"


class ApprovalRule(models.Model):
    """审核规则"""
    
    RULE_TYPES = [
        ('value_based', '基于价值'),
        ('time_based', '基于时间'),
        ('customer_based', '基于客户'),
        ('product_based', '基于产品'),
        ('department_based', '基于部门'),
    ]
    
    name = models.CharField('规则名称', max_length=100)
    rule_type = models.CharField('规则类型', max_length=20, choices=RULE_TYPES)
    conditions = models.JSONField('触发条件', default=dict)
    workflow_type = models.CharField('工作流类型', max_length=20, choices=ApprovalWorkflow.WORKFLOW_TYPES)
    is_active = models.BooleanField('是否激活', default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        db_table = 'approval_rule'
        verbose_name = '审核规则'
        verbose_name_plural = '审核规则'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"


class ApprovalEscalation(models.Model):
    """审核上报"""
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
    ]
    
    work_order = models.ForeignKey(
        'WorkOrder', 
        on_delete=models.CASCADE, 
        verbose_name='施工单',
        related_name='approval_escalations'
    )
    from_step = models.ForeignKey(
        ApprovalStep, 
        on_delete=models.CASCADE, 
        verbose_name='原步骤',
        related_name='escalations_from'
    )
    to_step = models.ForeignKey(
        ApprovalStep, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        verbose_name='目标步骤',
        related_name='escalations_to'
    )
    escalation_reason = models.TextField('上报原因')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    escalated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='上报人',
        related_name='escalated_approvals'
    )
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='处理人',
        related_name='resolved_approvals'
    )
    resolution_comments = models.TextField('处理意见', blank=True)
    resolved_at = models.DateTimeField('处理时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        db_table = 'approval_escalation'
        verbose_name = '审核上报'
        verbose_name_plural = '审核上报'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.work_order.order_number} - 上报"


class MultiLevelApprovalService:
    """多级审核服务类"""
    
    @classmethod
    def create_default_workflow(cls, workflow_type, user):
        """创建默认工作流"""
        workflow_configs = {
            'simple': {
                'name': '简单审核流程',
                'steps': [
                    {'step_name': '主管审核', 'assigned_role': 'supervisor'},
                ]
            },
            'standard': {
                'name': '标准审核流程',
                'steps': [
                    {'step_name': '主管审核', 'assigned_role': 'supervisor'},
                    {'step_name': '经理审核', 'assigned_role': 'manager'},
                ]
            },
            'complex': {
                'name': '复杂审核流程',
                'steps': [
                    {'step_name': '主管审核', 'assigned_role': 'supervisor'},
                    {'step_name': '经理审核', 'assigned_role': 'manager'},
                    {'step_name': '总监审核', 'assigned_role': 'director'},
                ]
            },
            'urgent': {
                'name': '紧急审核流程',
                'steps': [
                    {'step_name': '紧急处理', 'assigned_role': 'urgent_handler'},
                ]
            },
        }
        
        config = workflow_configs.get(workflow_type, workflow_configs['standard'])
        
        workflow = ApprovalWorkflow.objects.create(
            name=config['name'],
            workflow_type=workflow_type,
            steps=config['steps'],
            created_by=user
        )
        
        return workflow
    
    @classmethod
    def start_approval_process(cls, work_order, user):
        """启动审核流程"""
        workflow_type = cls.determine_workflow_type(work_order)
        
        # 获取或创建工作流
        workflow, created = ApprovalWorkflow.objects.get_or_create(
            workflow_type=workflow_type,
            defaults={
                'name': f'{workflow_type}_workflow',
                'created_by': user,
            }
        )
        
        if created:
            # 使用默认配置
            workflow = cls.create_default_workflow(workflow_type, user)
        
        # 创建审核步骤
        steps_data = workflow.steps
        approval_steps = []
        
        for i, step_data in enumerate(steps_data.get('steps', []), 1):
            step = ApprovalStep.objects.create(
                work_order=work_order,
                workflow=workflow,
                step_name=step_data['step_name'],
                step_order=i,
            )
            approval_steps.append(step)
        
        # 分配第一步给合适的用户
        if approval_steps:
            first_step = approval_steps[0]
            assigned_user = cls._get_step_assignee(first_step, work_order)
            if assigned_user:
                first_step.assigned_to = assigned_user
                first_step.save(update_fields=['assigned_to'])
        
        return approval_steps
    
    @classmethod
    def determine_workflow_type(cls, work_order):
        """确定工作流类型"""
        # 基于价值判断
        if work_order.total_amount >= 50000:
            return 'complex'
        elif work_order.total_amount >= 10000:
            return 'standard'
        elif work_order.priority == 'urgent':
            return 'urgent'
        else:
            return 'simple'
    
    @classmethod
    def complete_approval_step(cls, step, decision, comments, user):
        """完成审核步骤"""
        if step.status != 'in_progress':
            return False
        
        step.decision = decision
        step.comments = comments
        step.completed_at = timezone.now()
        
        if decision == 'escalate':
            step.status = 'completed'
            # 创建上报记录
            ApprovalEscalation.objects.create(
                work_order=step.work_order,
                from_step=step,
                escalation_reason=comments or '用户上报',
                escalated_by=user,
            )
        else:
            step.status = 'completed'
            
            # 如果是通过，检查是否还有下一步
            if decision == 'approve':
                next_step = ApprovalStep.objects.filter(
                    work_order=step.work_order,
                    step_order=step.step_order + 1
                ).first()
                
                if next_step:
                    # 分配下一步给合适的用户
                    assigned_user = cls._get_step_assignee(next_step, step.work_order)
                    if assigned_user:
                        next_step.assigned_to = assigned_user
                        next_step.status = 'pending'
                        next_step.save(update_fields=['assigned_to', 'status'])
        
        step.save(update_fields=['decision', 'comments', 'completed_at', 'status'])
        return True
    
    @classmethod
    def _get_step_assignee(cls, step, work_order):
        """获取步骤分配对象"""
        # 这里可以根据角色、部门等规则来分配
        # 暂时返回第一个有权限的用户
        return User.objects.filter(
            is_active=True,
            groups__name='supervisor'
        ).first()


class UrgentOrderService:
    """紧急订单服务类"""
    
    @classmethod
    def mark_as_urgent(cls, work_order, reason, user):
        """标记为紧急订单"""
        work_order.priority = 'urgent'
        work_order.save(update_fields=['priority'])
        
        # 记录紧急标记日志
        WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            action_type='mark_urgent',
            action_by=user,
            comments=reason,
        )
        
        return True
    
    @classmethod
    def calculate_urgency_level(cls, work_order):
        """计算紧急程度"""
        urgency_level = 1
        
        if work_order.priority == 'urgent':
            urgency_level += 3
        
        # 检查是否即将到期
        if work_order.deadline:
            days_remaining = (work_order.deadline - timezone.now().date()).days
            if days_remaining <= 1:
                urgency_level += 2
            elif days_remaining <= 3:
                urgency_level += 1
        
        return min(urgency_level, 5)  # 最高5级
    
    @classmethod
    def get_urgent_orders(cls):
        """获取紧急订单列表"""
        urgent_orders = WorkOrder.objects.filter(
            priority='urgent',
            status__in=['pending', 'in_progress']
        ).select_related('customer', 'created_by').order_by('-priority', 'deadline')
        
        return [
            {
                'id': order.id,
                'order_number': order.order_number,
                'customer_name': order.customer.name if order.customer else '',
                'priority': order.priority,
                'urgency_level': cls.calculate_urgency_level(order),
                'deadline': order.deadline,
                'created_at': order.created_at,
            }
            for order in urgent_orders
        ]