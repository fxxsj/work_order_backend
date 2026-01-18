"""
多级审核机制

实现灵活的多级审核流程：
1. 支持简单、标准、复杂订单的不同审核路径
2. 紧急订单快速通道
3. 审核流程配置化
4. 审核历史记录和追踪
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ApprovalWorkflow(models.Model):
    """审核工作流配置"""
    
    WORKFLOW_TYPES = [
        ('simple', '简单订单'),
        ('standard', '标准订单'),
        ('complex', '复杂订单'),
        ('urgent', '紧急订单'),
    ]
    
    name = models.CharField('工作流名称', max_length=100)
    workflow_type = models.CharField('工作流类型', max_length=20, choices=WORKFLOW_TYPES)
    description = models.TextField('描述', blank=True)
    
    # 审核步骤配置（JSON格式）
    steps = models.JSONField('审核步骤', default=list, help_text='审核步骤配置')
    
    # 是否启用
    is_active = models.BooleanField('是否启用', default=True)
    
    # 适用条件
    min_amount = models.DecimalField('最小金额', max_digits=12, decimal_places=2, null=True, blank=True)
    max_amount = models.DecimalField('最大金额', max_digits=12, decimal_places=2, null=True, blank=True)
    priority_filter = models.JSONField('优先级过滤', default=list, help_text='适用的优先级')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_workflows')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '审核工作流'
        verbose_name_plural = '审核工作流管理'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['workflow_type']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_workflow_type_display()})"

    def get_applicable_steps(self, work_order=None) -> List[Dict]:
        """获取适用的审核步骤"""
        if not self.is_active:
            return []
        
        steps = self.steps.copy()
        
        # 根据施工单信息过滤步骤
        if work_order:
            # 金额过滤
            if self.min_amount and work_order.total_amount < self.min_amount:
                return []
            if self.max_amount and work_order.total_amount > self.max_amount:
                return []
            
            # 优先级过滤
            if self.priority_filter and work_order.priority not in self.priority_filter:
                return []
        
        return steps


class ApprovalStep(models.Model):
    """审核步骤记录"""
    
    STEP_TYPES = [
        ('review', '审核'),
        ('approve', '批准'),
        ('reject', '拒绝'),
        ('escalate', '上报'),
    ]
    
    work_order = models.ForeignKey('WorkOrder', on_delete=models.CASCADE, related_name='approval_steps')
    workflow = models.ForeignKey(ApprovalWorkflow, on_delete=models.SET_NULL, null=True, related_name='workflow_steps')
    
    step_type = models.CharField('步骤类型', max_length=20, choices=STEP_TYPES)
    step_name = models.CharField('步骤名称', max_length=100)
    step_order = models.IntegerField('步骤顺序', default=0)
    
    # 执行人
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_approval_steps')
    role_filter = models.JSONField('角色过滤', default=list, help_text='适用角色列表')
    
    # 执行状态
    status = models.CharField('状态', max_length=20, choices=[
        ('pending', '待执行'),
        ('in_progress', '执行中'),
        ('completed', '已完成'),
        ('skipped', '已跳过'),
    ], default='pending')
    
    # 执行时间
    started_at = models.DateTimeField('开始时间', null=True, blank=True)
    completed_at = models.DateTimeField('完成时间', null=True, blank=True)
    
    # 执行结果
    decision = models.CharField('决定', max_length=20, choices=[
        ('approve', '批准'),
        ('reject', '拒绝'),
        ('escalate', '上报'),
    ], null=True, blank=True)
    
    comments = models.TextField('审核意见', blank=True)
    
    # 系统字段
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '审核步骤'
        verbose_name_plural = '审核步骤管理'
        ordering = ['work_order', 'step_order']
        unique_together = ['work_order', 'step_order']
        indexes = [
            models.Index(fields=['work_order', 'status']),
            models.Index(fields=['assigned_to', 'status']),
        ]

    def __str__(self):
        return f"{self.work_order.order_number} - {self.step_name}"


class ApprovalRule(models.Model):
    """审核规则配置"""
    
    RULE_TYPES = [
        ('amount_threshold', '金额阈值'),
        ('priority_match', '优先级匹配'),
        ('customer_type', '客户类型'),
        ('product_category', '产品类别'),
        ('custom_rule', '自定义规则'),
    ]
    
    workflow = models.ForeignKey(ApprovalWorkflow, on_delete=models.CASCADE, related_name='rules')
    rule_type = models.CharField('规则类型', max_length=20, choices=RULE_TYPES)
    rule_name = models.CharField('规则名称', max_length=100)
    
    # 规则配置（JSON格式）
    conditions = models.JSONField('规则条件', default=dict)
    actions = models.JSONField('规则动作', default=dict)
    
    is_active = models.BooleanField('是否启用', default=True)
    
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '审核规则'
        verbose_name_plural = '审核规则管理'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['workflow', 'rule_type']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.workflow.name} - {self.rule_name}"


class ApprovalEscalation(models.Model):
    """审核上报记录"""
    
    work_order = models.ForeignKey('WorkOrder', on_delete=models.CASCADE, related_name='escalations')
    from_step = models.ForeignKey(ApprovalStep, on_delete=models.SET_NULL, null=True, related_name='escalations_from')
    to_step = models.ForeignKey(ApprovalStep, on_delete=models.SET_NULL, null=True, related_name='escalations_to')
    
    escalation_reason = models.TextField('上报原因')
    escalation_level = models.IntegerField('上报级别', default=1)
    
    # 上报状态
    status = models.CharField('状态', max_length=20, choices=[
        ('pending', '待处理'),
        ('accepted', '已接受'),
        ('rejected', '已拒绝'),
        ('resolved', '已处理'),
    ], default='pending')
    
    escalated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='escalations_made')
    escalated_at = models.DateTimeField('上报时间', auto_now_add=True)
    
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='escalations_resolved')
    resolved_at = models.DateTimeField('处理时间', null=True, blank=True)
    
    resolution_comments = models.TextField('处理意见', blank=True)
    
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '审核上报'
        verbose_name_plural = '审核上报管理'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['work_order', 'status']),
            models.Index(fields=['escalated_by', 'status']),
        ]

    def __str__(self):
        return f"{self.work_order.order_number} - 上报记录#{self.id}"


class MultiLevelApprovalService:
    """多级审核服务"""
    
    @staticmethod
    def determine_workflow_type(work_order) -> str:
        """根据施工单信息确定审核流程类型"""
        # 紧急订单快速通道
        if work_order.priority == 'urgent':
            return 'urgent'
        
        # 根据金额确定复杂度
        if work_order.total_amount:
            if work_order.total_amount >= 100000:  # 10万以上
                return 'complex'
            elif work_order.total_amount >= 50000:  # 5万以上
                return 'standard'
        
        # 根据产品数量确定
        product_count = work_order.products.count()
        if product_count >= 10:
            return 'complex'
        elif product_count >= 5:
            return 'standard'
        
        # 根据工序复杂度确定
        complex_processes = work_order.order_processes.filter(
            process__code__in=['FOIL_G', 'EMB', 'DIE']  # 烫金、压凸、模切
        ).count()
        if complex_processes >= 2:
            return 'complex'
        elif complex_processes >= 1:
            return 'standard'
        
        return 'simple'
    
    @staticmethod
    def create_approval_workflow(work_order, creator=None) -> ApprovalWorkflow:
        """为施工单创建审核工作流"""
        workflow_type = MultiLevelApprovalService.determine_workflow_type(work_order)
        
        # 获取适用的工作流
        workflow = ApprovalWorkflow.objects.filter(
            workflow_type=workflow_type,
            is_active=True
        ).first()
        
        if not workflow:
            # 创建默认工作流
            workflow = MultiLevelApprovalService.create_default_workflow(workflow_type, creator)
        
        return workflow
    
    @staticmethod
    def create_default_workflow(workflow_type: str, creator=None) -> ApprovalWorkflow:
        """创建默认工作流配置"""
        default_workflows = {
            'simple': {
                'name': '简单订单审核',
                'steps': [
                    {
                        'step_type': 'review',
                        'step_name': '业务员审核',
                        'step_order': 1,
                        'role_filter': ['业务员'],
                        'required': True
                    }
                ]
            },
            'standard': {
                'name': '标准订单审核',
                'steps': [
                    {
                        'step_type': 'review',
                        'step_name': '业务员初审',
                        'step_order': 1,
                        'role_filter': ['业务员'],
                        'required': True
                    },
                    {
                        'step_type': 'approve',
                        'step_name': '主管审批',
                        'step_order': 2,
                        'role_filter': ['主管'],
                        'required': True
                    }
                ]
            },
            'complex': {
                'name': '复杂订单审核',
                'steps': [
                    {
                        'step_type': 'review',
                        'step_name': '业务员初审',
                        'step_order': 1,
                        'role_filter': ['业务员'],
                        'required': True
                    },
                    {
                        'step_type': 'approve',
                        'step_name': '主管审批',
                        'step_order': 2,
                        'role_filter': ['主管'],
                        'required': True
                    },
                    {
                        'step_type': 'approve',
                        'step_name': '经理审批',
                        'step_order': 3,
                        'role_filter': ['经理'],
                        'required': True
                    }
                ]
            },
            'urgent': {
                'name': '紧急订单快速通道',
                'steps': [
                    {
                        'step_type': 'approve',
                        'step_name': '主管直审',
                        'step_order': 1,
                        'role_filter': ['主管', '经理'],
                        'required': True
                    }
                ]
            }
        }
        
        config = default_workflows.get(workflow_type, default_workflows['simple'])
        
        return ApprovalWorkflow.objects.create(
            name=config['name'],
            workflow_type=workflow_type,
            description=f'自动创建的{workflow_type}工作流',
            steps=config['steps'],
            created_by=creator
        )
    
    @staticmethod
    @transaction.atomic
    def start_approval_process(work_order, creator=None) -> List[ApprovalStep]:
        """启动审核流程"""
        # 确定工作流
        workflow = MultiLevelApprovalService.create_approval_workflow(work_order, creator)
        
        # 创建审核步骤
        steps_config = workflow.get_applicable_steps(work_order)
        approval_steps = []
        
        for step_config in steps_config:
            # 查找执行人
            assigned_to = MultiLevelApprovalService.find_step_assignee(
                work_order, step_config, creator
            )
            
            step = ApprovalStep.objects.create(
                work_order=work_order,
                workflow=workflow,
                step_type=step_config['step_type'],
                step_name=step_config['step_name'],
                step_order=step_config['step_order'],
                assigned_to=assigned_to,
                role_filter=step_config.get('role_filter', []),
                status='pending'
            )
            
            approval_steps.append(step)
        
        # 更新施工单审核状态
        work_order.approval_status = 'pending'
        work_order.save(update_fields=['approval_status'])
        
        # 创建通知
        MultiLevelApprovalService.create_approval_notifications(work_order, approval_steps)
        
        return approval_steps
    
    @staticmethod
    def find_step_assignee(work_order, step_config: Dict, creator=None) -> Optional[User]:
        """查找步骤执行人"""
        role_filter = step_config.get('role_filter', [])
        
        if not role_filter:
            return creator
        
        # 根据角色查找用户
        from django.contrib.auth.models import Group
        from django.db.models import Q
        
        # 构建查询条件
        user_query = Q()
        if '业务员' in role_filter:
            user_query |= Q(groups__name='业务员')
        if '主管' in role_filter:
            user_query |= Q(groups__name='主管')
        if '经理' in role_filter:
            user_query |= Q(groups__name='经理')
        
        # 优先选择工作订单的业务员或主管
        if work_order.customer and work_order.customer.salesperson:
            if work_order.customer.salesperson.groups.filter(name__in=role_filter).exists():
                return work_order.customer.salesperson
        
        # 否则选择符合角色的第一个用户
        users = User.objects.filter(user_query, is_active=True).order_by('id')
        return users.first()
    
    @staticmethod
    def complete_approval_step(step, decision: str, comments: str = '', user=None) -> bool:
        """完成审核步骤"""
        if step.status == 'completed':
            return False
        
        # 更新步骤状态
        step.status = 'completed'
        step.decision = decision
        step.comments = comments
        step.completed_at = timezone.now()
        step.save(update_fields=['status', 'decision', 'comments', 'completed_at'])
        
        # 检查是否需要继续下一步
        work_order = step.work_order
        remaining_steps = work_order.approval_steps.filter(
            status__in=['pending', 'in_progress']
        ).exclude(step_order__lte=step.step_order)
        
        if not remaining_steps.exists():
            # 所有步骤完成，更新施工单状态
            if decision == 'approve':
                work_order.approval_status = 'approved'
                work_order.approved_by = user
                work_order.approved_at = timezone.now()
            elif decision == 'reject':
                work_order.approval_status = 'rejected'
                work_order.approved_by = user
                work_order.approved_at = timezone.now()
            elif decision == 'escalate':
                work_order.approval_status = 'pending'  # 保持待审核状态
                work_order.approved_by = None
                work_order.approved_at = None
            
            work_order.save(update_fields=[
                'approval_status', 'approved_by', 'approved_at'
            ])
            
            # 创建最终通知
            MultiLevelApprovalService.create_final_notification(work_order, decision)
        
        return True
    
    @staticmethod
    def create_approval_notifications(work_order, steps: List[ApprovalStep]):
        """创建审核通知"""
        from ..models.system import Notification
        
        for step in steps:
            if step.assigned_to:
                Notification.objects.create(
                    recipient=step.assigned_to,
                    notification_type='approval_request',
                    title=f'待审核：{step.step_name}',
                    content=f'施工单 {work_order.order_number} 需要您的审核',
                    priority='normal' if work_order.priority != 'urgent' else 'high',
                    work_order=work_order,
                    approval_step=step
                )
    
    @staticmethod
    def create_final_notification(work_order, decision: str):
        """创建最终审核结果通知"""
        from ..models.system import Notification
        
        # 通知创建人
        if work_order.created_by:
            Notification.objects.create(
                recipient=work_order.created_by,
                notification_type='approval_result',
                title=f'审核结果：{work_order.order_number}',
                content=f'您的施工单审核{decision == "approve" ? "通过" : "被拒绝"}',
                priority='high',
                work_order=work_order
            )
        
        # 通知所有审核参与者
        participants = User.objects.filter(
            approval_steps__work_order=work_order,
            approval_steps__status='completed'
        ).distinct()
        
        for participant in participants:
            Notification.objects.create(
                recipient=participant,
                notification_type='approval_completed',
                title=f'审核完成：{work_order.order_number}',
                content=f'施工单 {work_order.order_number} 审核流程已结束，结果：{decision == "approve" ? "通过" : "拒绝"}',
                priority='high',
                work_order=work_order
            )
    
    @staticmethod
    def can_edit_approved_order(work_order, user) -> Dict[str, Any]:
        """检查是否可以编辑已审核的订单"""
        if work_order.approval_status != 'approved':
            return {'can_edit': True, 'reason': '订单未审核'}
        
        # 检查用户权限
        if user.is_superuser:
            return {'can_edit': True, 'reason': '超级管理员'}
        
        # 检查是否是最终审核人
        final_step = work_order.approval_steps.order_by('-step_order').first()
        if final_step and final_step.assigned_to == user:
            return {'can_edit': True, 'reason': '最终审核人'}
        
        # 检查特殊权限
        if user.has_perm('workorder.change_approved_workorder'):
            return {'can_edit': True, 'reason': '有编辑权限'}
        
        return {
            'can_edit': False, 
            'reason': '已审核的订单，权限不足',
            'allowed_fields': ['notes', 'delivery_date', 'actual_delivery_date', 'priority']
        }


class UrgentOrderService:
    """紧急订单服务"""
    
    @staticmethod
    def mark_as_urgent(work_order, reason: str = '', user=None) -> bool:
        """标记为紧急订单"""
        if work_order.priority != 'urgent':
            # 记录优先级变更日志
            from ..models.system import SystemLog
            
            SystemLog.objects.create(
                log_type='priority_change',
                content=f'施工单 {work_order.order_number} 标记为紧急订单',
                details={
                    'old_priority': work_order.priority,
                    'new_priority': 'urgent',
                    'reason': reason,
                    'changed_by': user.username if user else None
                },
                work_order=work_order,
                user=user
            )
            
            # 更新优先级
            work_order.priority = 'urgent'
            work_order.save(update_fields=['priority'])
            
            # 重新启动紧急审核流程
            MultiLevelApprovalService.start_approval_process(work_order, user)
            
            # 发送紧急通知
            UrgentOrderService.send_urgent_notification(work_order)
            
            return True
        
        return False
    
    @staticmethod
    def send_urgent_notification(work_order):
        """发送紧急订单通知"""
        from ..models.system import Notification
        
        # 通知所有主管和经理
        managers = User.objects.filter(
            groups__name__in=['主管', '经理'],
            is_active=True
        )
        
        for manager in managers:
            Notification.objects.create(
                recipient=manager,
                notification_type='urgent_order',
                title=f'紧急订单：{work_order.order_number}',
                content=f'施工单 {work_order.order_number} 已标记为紧急，请优先处理',
                priority='urgent',
                work_order=work_order
            )
    
    @staticmethod
    def get_urgent_orders() -> List[Dict]:
        """获取紧急订单列表"""
        from ..models.core import WorkOrder
        
        urgent_orders = WorkOrder.objects.filter(
            priority='urgent',
            approval_status__in=['pending', 'approved']
        ).prefetch_related(
            'customer',
            'order_processes__process',
            'products__product'
        ).order_by('-created_at')
        
        result = []
        for order in urgent_orders:
            result.append({
                'id': order.id,
                'order_number': order.order_number,
                'customer_name': order.customer.name if order.customer else '',
                'total_amount': order.total_amount,
                'priority': order.priority,
                'approval_status': order.approval_status,
                'created_at': order.created_at,
                'urgency_level': UrgentOrderService.calculate_urgency_level(order)
            })
        
        return result
    
    @staticmethod
    def calculate_urgency_level(work_order) -> str:
        """计算紧急程度"""
        if work_order.priority != 'urgent':
            return 'normal'
        
        # 根据交货日期计算紧急程度
        if work_order.delivery_date:
            days_until_delivery = (work_order.delivery_date - timezone.now().date()).days
            if days_until_delivery <= 1:
                return 'critical'
            elif days_until_delivery <= 3:
                return 'high'
            elif days_until_delivery <= 7:
                return 'medium'
        
        return 'low'