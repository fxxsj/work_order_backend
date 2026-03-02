"""
通知触发器

在关键业务事件发生时自动触发通知
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from ..models.core import WorkOrder, WorkOrderProcess, WorkOrderTask, ProcessLog
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
    # Check if operator was assigned (not just department)
    if instance.assigned_operator:
        notification_service.notify_task_assigned(
            task=instance,
            assigned_operator=instance.assigned_operator,
            assigned_by=instance.updated_by if hasattr(instance, 'updated_by') else None
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
                        recipients=[instance.assigned_operator, instance.work_order_process.work_order.created_by] if instance.assigned_operator else [instance.work_order_process.work_order.created_by],
                        data={
                            'title': '任务开始执行',
                            'message': f'任务 {instance.work_content} 已开始执行',
                            'task_id': instance.id,
                            'task_name': instance.work_content,
                            'workorder_id': instance.work_order_process.work_order.id,
                            'workorder_number': instance.work_order_process.work_order.order_number,
                            'assigned_to': instance.assigned_operator.username if instance.assigned_operator else ''
                        },
                        priority=NotificationPriority.NORMAL
                    )
                
                elif new_status == 'completed':
                    # 任务完成 - 通知主管和创建者
                    notification_service.notify_task_completed(
                        task=instance,
                        completed_by=instance.assigned_operator if instance.assigned_operator else instance.updated_by
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
    if not created:
        return

    if instance.log_type != "complete":
        return

    workorder_process = instance.work_order_process
    if not workorder_process:
        return

    notification_service.notify_process_completion(
        process=workorder_process.process,
        workorder=workorder_process.work_order,
        completed_by=instance.operator,
    )


class DeadlineWarningService:
    """交货期预警服务"""
    
    @staticmethod
    def check_deadline_warnings():
        """检查并发送交货期预警"""
        from datetime import date
        
        today = date.today()
        
        # 检查1天后到期的施工单（使用交货日期）
        one_day_later = today + timedelta(days=1)
        workorders_1_day = WorkOrder.objects.filter(
            delivery_date=one_day_later,
            status__in=['pending', 'in_progress']
        )
        
        for workorder in workorders_1_day:
            notification_service.notify_deadline_warning(workorder, 1)
        
        # 检查3天后到期的施工单（使用交货日期）
        three_days_later = today + timedelta(days=3)
        workorders_3_days = WorkOrder.objects.filter(
            delivery_date=three_days_later,
            status__in=['pending', 'in_progress']
        )
        
        for workorder in workorders_3_days:
            notification_service.notify_deadline_warning(workorder, 3)
    
    @staticmethod
    def check_overdue_tasks():
        """检查逾期任务"""
        now = timezone.now()
        
        # 检查逾期但未完成的任务（使用工序计划结束时间）
        overdue_tasks = WorkOrderTask.objects.filter(
            work_order_process__planned_end_time__lt=now,
            status__in=["pending", "in_progress"],
        )
        
        for task in overdue_tasks:
            recipients = [task.work_order_process.work_order.created_by]
            if task.assigned_operator:
                recipients.append(task.assigned_operator)

            notification_service.send_notification(
                event_type=NotificationEvent.TASK_OVERDUE,
                recipients=recipients,
                data={
                    'title': '任务逾期警告',
                    'message': f'任务 {task.work_content} 已逾期',
                    'task_id': task.id,
                    'task_name': task.work_content,
                    'workorder_id': task.work_order_process.work_order.id,
                    'workorder_number': task.work_order_process.work_order.order_number,
                    'deadline': (
                        task.work_order_process.planned_end_time.isoformat()
                        if task.work_order_process and task.work_order_process.planned_end_time
                        else None
                    ),
                    'assigned_to': task.assigned_operator.username if task.assigned_operator else ''
                },
                priority=NotificationPriority.URGENT
            )
    
    @staticmethod
    def send_workorder_update_notification(workorder, updated_fields, updated_by=None):
        """发送施工单更新通知"""
        # 只对重要字段发送通知
        important_fields = ["status", "priority", "delivery_date", "total_amount"]
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


def check_deadline_warnings():
    """供外部调度的交货期预警入口"""
    DeadlineWarningService.check_deadline_warnings()


def check_overdue_tasks():
    """供外部调度的任务逾期检查入口"""
    DeadlineWarningService.check_overdue_tasks()


def _get_supervisors():
    """获取主管列表"""
    try:
        return User.objects.filter(
            groups__name='supervisor',
            is_active=True
        ).distinct()
    except Exception:
        return []
