"""
系统相关模型

包含系统管理相关模型：
- UserProfile: 用户扩展信息
- WorkOrderApprovalLog: 施工单审核历史记录
- Notification: 系统通知
- TaskAssignmentRule: 任务分派规则配置
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .base import Department
from .core import WorkOrder

class UserProfile(models.Model):
    """用户扩展信息"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile',
                                verbose_name='用户')
    departments = models.ManyToManyField(Department, blank=True,
                                        verbose_name='所属部门', help_text='用户所属的部门（可多选）')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '用户扩展信息'
        verbose_name_plural = '用户扩展信息管理'

    def __str__(self):
        if self.pk and self.departments.exists():
            dept_names = ', '.join([dept.name for dept in self.departments.all()])
            return f"{self.user.username} - {dept_names}"
        return f"{self.user.username} - 未分配部门"

class WorkOrderApprovalLog(models.Model):
    """施工单审核历史记录"""
    work_order = models.ForeignKey('workorder.WorkOrder', on_delete=models.CASCADE,
                                   related_name='approval_logs', verbose_name='施工单')
    approval_status = models.CharField('审核状态', max_length=20, 
                                     choices=WorkOrder.APPROVAL_STATUS_CHOICES)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                   null=True, blank=True,
                                   related_name='approval_logs', verbose_name='审核人')
    approved_at = models.DateTimeField('审核时间', auto_now_add=True)
    approval_comment = models.TextField('审核意见', blank=True, 
                                       help_text='审核意见或说明')
    rejection_reason = models.TextField('拒绝原因', blank=True, 
                                       help_text='审核拒绝时的拒绝原因')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '施工单审核历史'
        verbose_name_plural = '施工单审核历史管理'
        ordering = ['-approved_at', '-created_at']

    def __str__(self):
        status_display = dict(WorkOrder.APPROVAL_STATUS_CHOICES).get(self.approval_status, self.approval_status)
        return f"{self.work_order.order_number} - {status_display} - {self.approved_by.username if self.approved_by else '未知'}"

class Notification(models.Model):
    """系统通知"""
    NOTIFICATION_TYPE_CHOICES = [
        ('approval_passed', '审核通过'),
        ('approval_rejected', '审核拒绝'),
        ('reapproval_requested', '请求重新审核'),
        ('task_assigned', '任务分派'),
        ('task_due_soon', '任务即将到期'),
        ('process_completed', '工序完成'),
        ('workorder_completed', '施工单完成'),
        ('task_cancelled', '任务取消'),
        ('purchase_order_submitted', '采购单待审核'),
        ('purchase_order_approved', '采购单已批准'),
        ('purchase_order_rejected', '采购单已拒绝'),
        ('purchase_order_received', '采购单已收货'),
        ('low_stock_warning', '库存不足预警'),
        ('system', '系统通知'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', '低'),
        ('normal', '普通'),
        ('high', '高'),
        ('urgent', '紧急'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE,
                                 related_name='notifications', verbose_name='接收人')
    notification_type = models.CharField('通知类型', max_length=30, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField('标题', max_length=200)
    content = models.TextField('内容', help_text='通知详细内容')
    priority = models.CharField('优先级', max_length=10, choices=PRIORITY_CHOICES, default='normal')
    
    # 关联对象（可选，用于跳转到相关页面）
    work_order = models.ForeignKey('workorder.WorkOrder', on_delete=models.CASCADE, null=True, blank=True,
                                   related_name='notifications', verbose_name='关联施工单')
    work_order_process = models.ForeignKey('workorder.WorkOrderProcess', on_delete=models.CASCADE, null=True, blank=True,
                                         related_name='notifications', verbose_name='关联工序')
    task = models.ForeignKey('workorder.WorkOrderTask', on_delete=models.CASCADE, null=True, blank=True,
                            related_name='notifications', verbose_name='关联任务')
    purchase_order = models.ForeignKey('workorder.PurchaseOrder', on_delete=models.CASCADE, null=True, blank=True,
                                       related_name='notifications', verbose_name='关联采购单')
    
    # 通知状态
    is_read = models.BooleanField('已读', default=False)
    read_at = models.DateTimeField('阅读时间', null=True, blank=True)
    is_sent = models.BooleanField('已发送', default=False)

    # 元数据
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    expires_at = models.DateTimeField('过期时间', null=True, blank=True,
                                     help_text='通知过期时间，过期后不再显示')
    data = models.JSONField('扩展数据', null=True, blank=True)
    
    class Meta:
        verbose_name = '系统通知'
        verbose_name_plural = '系统通知管理'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.recipient.username} - {self.title}"
    
    def mark_as_read(self):
        """标记为已读"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    @classmethod
    def create_notification(cls, recipient, notification_type, title, content, 
                           priority='normal', work_order=None, work_order_process=None, 
                           task=None, expires_at=None):
        """创建通知的便捷方法"""
        return cls.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            content=content,
            priority=priority,
            work_order=work_order,
            work_order_process=work_order_process,
            task=task,
            expires_at=expires_at
        )

class TaskAssignmentRule(models.Model):
    """任务分派规则配置"""
    OPERATOR_SELECTION_STRATEGY_CHOICES = [
        ('least_tasks', '任务数量最少（工作量均衡）'),
        ('random', '随机选择'),
        ('round_robin', '轮询分配'),
        ('first_available', '第一个可用'),
    ]
    
    process = models.ForeignKey('workorder.Process', on_delete=models.CASCADE,
                               related_name='assignment_rules', verbose_name='工序',
                               help_text='该规则适用的工序')
    department = models.ForeignKey('workorder.Department', on_delete=models.CASCADE,
                                  related_name='assignment_rules', verbose_name='分派部门',
                                  help_text='该工序应分派到的部门')
    priority = models.IntegerField('优先级', default=0,
                                  help_text='优先级越高越优先匹配（0-100）')
    operator_selection_strategy = models.CharField('操作员选择策略', max_length=20,
                                                   choices=OPERATOR_SELECTION_STRATEGY_CHOICES,
                                                   default='least_tasks',
                                                   help_text='从部门中选择操作员的策略')
    is_active = models.BooleanField('是否启用', default=True,
                                   help_text='是否启用该规则')
    notes = models.TextField('备注', blank=True,
                            help_text='规则说明或备注')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = '任务分派规则'
        verbose_name_plural = '任务分派规则管理'
        ordering = ['process', '-priority', 'department']
        unique_together = [['process', 'department']]  # 同一工序同一部门只能有一条规则

    def __str__(self):
        return f"{self.process.name} -> {self.department.name} (优先级:{self.priority})"

