"""
通知触发器

在关键业务事件发生时自动触发通知
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from ..models.core import WorkOrder, WorkOrderProcess, WorkOrderTask, ProcessLog, TaskLog
from ..models.system import WorkOrderApprovalLog
from ..services.realtime_notification import (
    notification_service, NotificationEvent, NotificationPriority
)


@receiver(post_save, sender=WorkOrder)
def workorder_created_handler(sender, instance, created, **kwargs):
    """施工单创建时触发通知"""
    if created:
        # 通知主管有新施工单
        notification_service.send_notification(
            event_type=NotificationEvent.WORKORDER_CREATED,
            recipients=_get_supervisors(),
            data={
                'title': '新施工单创建',
                'message': f'新施工单 {instance.order_number} 已创建',
                'workorder_id': instance.id,
                'workorder_number': instance.order_number,
                'customer': instance.customer.name if instance.customer else '',
                'total_amount': instance.total_amount,
                'priority': instance.priority
            },
            priority=NotificationPriority.NORMAL
        )


@receiver(post_save, sender=WorkOrderTask)
def task_assigned_handler(sender, instance, created, **kwargs):
    """任务分配时触发通知"""
    if created and instance.assigned_to:
        notification_service.notify_task_assignment(
            task=instance,
            assigned_user=instance.assigned_to,
            assigned_by=instance.created_by
        )


@receiver(pre_save, sender=WorkOrderTask)
def task_status_change_handler(sender, instance, **kwargs):
    """任务状态变更时触发通知"""
    if instance.pk:
        try:
            old_instance = WorkOrderTask.objects.get(pk=instance.pk)
            old_status = old_instance.status
            new_status = instance.status
            
            if old_status != new_status:
                if new_status == 'in_progress' and old_status == 'pending':
                    # 任务开始
                    notification_service.send_notification(
                        event_type=NotificationEvent.TASK_STARTED,
                        recipients=[instance.assigned_to, instance.workorder.created_by],
                        data={
                            'title': '任务开始执行',
                            'message': f'任务 {instance.task_name} 已开始执行',
                            'task_id': instance.id,
                            'task_name': instance.task_name,
                            'workorder_id': instance.workorder.id,
                            'workorder_number': instance.workorder.order_number,
                            'assigned_to': instance.assigned_to.username if instance.assigned_to else ''
                        },
                        priority=NotificationPriority.NORMAL
                    )
                
                elif new_status == 'completed':
                    # 任务完成
                    notification_service.send_notification(
                        event_type=NotificationEvent.TASK_COMPLETED,
                        recipients=[instance.workorder.created_by],
                        data={
                            'title': '任务完成',
                            'message': f'任务 {instance.task_name} 已完成',
                            'task_id': instance.id,
                            'task_name': instance.task_name,
                            'workorder_id': instance.workorder.id,
                            'workorder_number': instance.workorder.order_number,
                            'completed_at': instance.completed_at.isoformat() if instance.completed_at else None
                        },
                        priority=NotificationPriority.HIGH
                    )
                    
        except WorkOrderTask.DoesNotExist:
            pass


@receiver(post_save, sender=WorkOrderApprovalLog)
def approval_log_handler(sender, instance, created, **kwargs):
    """审核日志创建时触发通知"""
    if created:
        if instance.action_type in ['approve', 'reject']:
            notification_service.notify_workorder_approval(
                workorder=instance.work_order,
                status='approved' if instance.action_type == 'approve' else 'rejected',
                approved_by=instance.action_by
            )


@receiver(post_save, sender=ProcessLog)
def process_log_handler(sender, instance, created, **kwargs):
    """工序日志创建时触发通知"""
    if created:
        if instance.action_type == 'completed':
            # 工序完成
            try:
                workorder_process = WorkOrderProcess.objects.get(
                    workorder=instance.work_order,
                    process=instance.process
                )
                
                notification_service.notify_process_completion(
                    process=instance.process,
                    workorder=instance.work_order,
                    completed_by=instance.created_by
                )
                
            except WorkOrderProcess.DoesNotExist:
                pass
        
        elif instance.action_type == 'error':
            # 工序出错
            notification_service.send_notification(
                event_type=NotificationEvent.PROCESS_ERROR,
                recipients=[instance.work_order.created_by] + _get_supervisors(),
                data={
                    'title': '工序执行出错',
                    'message': f'工序 {instance.process.name} 执行过程中出现错误',
                    'process_id': instance.process.id,
                    'process_name': instance.process.name,
                    'workorder_id': instance.work_order.id,
                    'workorder_number': instance.work_order.order_number,
                    'error_message': instance.comments,
                    'created_by': instance.created_by.username if instance.created_by else ''
                },
                priority=NotificationPriority.HIGH
            )


@receiver(post_save, sender=TaskLog)
def task_log_handler(sender, instance, created, **kwargs):
    """任务日志创建时触发通知"""
    if created:
        if instance.action_type == 'error':
            # 任务出错
            notification_service.send_notification(
                event_type=NotificationEvent.TASK_ERROR,
                recipients=[instance.task.workorder.created_by] + _get_supervisors(),
                data={
                    'title': '任务执行出错',
                    'message': f'任务 {instance.task.task_name} 执行过程中出现错误',
                    'task_id': instance.task.id,
                    'task_name': instance.task.task_name,
                    'workorder_id': instance.task.workorder.id,
                    'workorder_number': instance.task.workorder.order_number,
                    'error_message': instance.comments,
                    'created_by': instance.created_by.username if instance.created_by else ''
                },
                priority=NotificationPriority.HIGH
            )


class DeadlineWarningService:
    """交货期预警服务"""
    
    @staticmethod
    def check_deadline_warnings():
        """检查并发送交货期预警"""
        from datetime import date
        
        today = date.today()
        
        # 检查1天后到期的施工单
        one_day_later = today + timedelta(days=1)
        workorders_1_day = WorkOrder.objects.filter(
            deadline=one_day_later,
            status__in=['pending', 'in_progress']
        )
        
        for workorder in workorders_1_day:
            notification_service.notify_deadline_warning(workorder, 1)
        
        # 检查3天后到期的施工单
        three_days_later = today + timedelta(days=3)
        workorders_3_days = WorkOrder.objects.filter(
            deadline=three_days_later,
            status__in=['pending', 'in_progress']
        )
        
        for workorder in workorders_3_days:
            notification_service.notify_deadline_warning(workorder, 3)
    
    @staticmethod
    def check_overdue_tasks():
        """检查逾期任务"""
        now = timezone.now()
        
        # 检查逾期但未完成的任务
        overdue_tasks = WorkOrderTask.objects.filter(
            deadline__lt=now,
            status__in=['pending', 'in_progress']
        )
        
        for task in overdue_tasks:
            notification_service.send_notification(
                event_type=NotificationEvent.TASK_OVERDUE,
                recipients=[task.assigned_to, task.workorder.created_by],
                data={
                    'title': '任务逾期警告',
                    'message': f'任务 {task.task_name} 已逾期',
                    'task_id': task.id,
                    'task_name': task.task_name,
                    'workorder_id': task.workorder.id,
                    'workorder_number': task.workorder.order_number,
                    'deadline': task.deadline.isoformat() if task.deadline else None,
                    'assigned_to': task.assigned_to.username if task.assigned_to else ''
                },
                priority=NotificationPriority.URGENT
            )


class NotificationIntegrationService:
    """通知集成服务"""
    
    @staticmethod
    def initialize():
        """初始化通知集成"""
        # 这里可以设置定时任务
        from celery import Celery
        from django.conf import settings
        
        app = Celery('workorder')
        
        # 设置定时检查交货期预警
        @app.task
        def check_deadline_warnings():
            DeadlineWarningService.check_deadline_warnings()
        
        @app.task
        def check_overdue_tasks():
            DeadlineWarningService.check_overdue_tasks()
        
        # 每天早上8点检查交货期预警
        app.conf.beat_schedule = {
            'check-deadline-warnings': {
                'task': 'workorder.services.notification_triggers.check_deadline_warnings',
                'schedule': 86400.0,  # 24小时
            },
            'check-overdue-tasks': {
                'task': 'workorder.services.notification_triggers.check_overdue_tasks',
                'schedule': 3600.0,  # 1小时
            },
        }
    
    @staticmethod
    def send_workorder_update_notification(workorder, updated_fields, updated_by=None):
        """发送施工单更新通知"""
        # 只对重要字段发送通知
        important_fields = ['status', 'priority', 'deadline', 'total_amount']
        notified_fields = []
        
        for field in updated_fields:
            if field in important_fields:
                notified_fields.append(field)
        
        if notified_fields:
            recipients = [workorder.created_by]
            
            # 如果状态变更，也通知主管
            if 'status' in notified_fields:
                recipients.extend(_get_supervisors())
            
            notification_service.send_notification(
                event_type=NotificationEvent.WORKORDER_UPDATED,
                recipients=list(set(recipients)),
                data={
                    'title': '施工单信息更新',
                    'message': f'施工单 {workorder.order_number} 的信息已更新',
                    'workorder_id': workorder.id,
                    'workorder_number': workorder.order_number,
                    'updated_fields': notified_fields,
                    'updated_by': updated_by.username if updated_by else '系统'
                },
                priority=NotificationPriority.NORMAL
            )


def _get_supervisors():
    """获取主管列表"""
    try:
        return User.objects.filter(
            groups__name='supervisor',
            is_active=True
        ).distinct()
    except Exception:
        return []


# 初始化通知集成
NotificationIntegrationService.initialize()