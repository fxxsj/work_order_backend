"""
实时通知服务

提供WebSocket实时通知、事件驱动的通知发送、通知管理等功能
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync, sync_to_async
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class NotificationEvent:
    """通知事件定义"""
    
    # 工序相关事件
    PROCESS_STARTED = 'process_started'
    PROCESS_COMPLETED = 'process_completed'
    PROCESS_PAUSED = 'process_paused'
    PROCESS_ERROR = 'process_error'
    
    # 任务相关事件
    TASK_ASSIGNED = 'task_assigned'
    TASK_STARTED = 'task_started'
    TASK_COMPLETED = 'task_completed'
    TASK_OVERDUE = 'task_overdue'
    
    # 施工单相关事件
    WORKORDER_CREATED = 'workorder_created'
    WORKORDER_UPDATED = 'workorder_updated'
    WORKORDER_APPROVED = 'workorder_approved'
    WORKORDER_REJECTED = 'workorder_rejected'
    WORKORDER_COMPLETED = 'workorder_completed'
    
    # 审核相关事件
    APPROVAL_STEP_STARTED = 'approval_step_started'
    APPROVAL_STEP_COMPLETED = 'approval_step_completed'
    APPROVAL_ESCALATED = 'approval_escalated'
    
    # 系统相关事件
    SYSTEM_ANNOUNCEMENT = 'system_announcement'
    DEADLINE_WARNING = 'deadline_warning'
    URGENT_ORDER = 'urgent_order'


class NotificationPriority:
    """通知优先级"""
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    URGENT = 'urgent'


class NotificationChannel:
    """通知渠道"""
    WEBSOCKET = 'websocket'
    EMAIL = 'email'
    SMS = 'sms'
    IN_APP = 'in_app'


class RealtimeNotificationService:
    """实时通知服务"""
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
        
    def send_notification(self, event_type: str, recipients: List[User], 
                        data: Dict[str, Any], priority: str = NotificationPriority.NORMAL,
                        channels: List[str] = None):
        """
        发送通知
        
        Args:
            event_type: 事件类型
            recipients: 接收者列表
            data: 通知数据
            priority: 优先级
            channels: 通知渠道列表
        """
        if channels is None:
            channels = [NotificationChannel.WEBSOCKET, NotificationChannel.IN_APP]
        
        notification_data = {
            'event_type': event_type,
            'priority': priority,
            'data': data,
            'timestamp': timezone.now().isoformat(),
            'channels': channels
        }
        
        # 保存到数据库
        self._save_notification_to_db(recipients, notification_data)
        
        # 发送WebSocket通知
        if NotificationChannel.WEBSOCKET in channels:
            self._send_websocket_notification(recipients, notification_data)
        
        # 发送邮件通知（如果是高优先级或紧急）
        if (NotificationChannel.EMAIL in channels and 
            priority in [NotificationPriority.HIGH, NotificationPriority.URGENT]):
            self._send_email_notification(recipients, notification_data)
    
    def _save_notification_to_db(self, recipients: List[User], data: Dict[str, Any]):
        """保存通知到数据库"""
        try:
            from ..models.system import Notification
            
            notifications = []
            for recipient in recipients:
                notifications.append(Notification(
                    user=recipient,
                    event_type=data['event_type'],
                    priority=data['priority'],
                    title=data['data'].get('title', ''),
                    message=data['data'].get('message', ''),
                    data=data,
                    is_read=False
                ))
            
            Notification.objects.bulk_create(notifications)
            
        except Exception as e:
            logger.error(f"保存通知到数据库失败: {e}")
    
    def _send_websocket_notification(self, recipients: List[User], data: Dict[str, Any]):
        """发送WebSocket通知"""
        try:
            for recipient in recipients:
                group_name = f"user_{recipient.id}_notifications"
                
                async_to_sync(self.channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'notification_message',
                        'notification': data
                    }
                )
        except Exception as e:
            logger.error(f"发送WebSocket通知失败: {e}")
    
    def _send_email_notification(self, recipients: List[User], data: Dict[str, Any]):
        """发送邮件通知"""
        try:
            from django.core.mail import send_mail
            from django.template.loader import render_to_string
            
            for recipient in recipients:
                subject = data['data'].get('title', '系统通知')
                message = data['data'].get('message', '')
                
                html_message = render_to_string('notifications/email_template.html', {
                    'user': recipient,
                    'notification': data,
                    'data': data['data']
                })
                
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient.email],
                    html_message=html_message,
                    fail_silently=True
                )
        except Exception as e:
            logger.error(f"发送邮件通知失败: {e}")
    
    def notify_task_assignment(self, task, assigned_user, assigned_by=None):
        """通知任务分配"""
        self.send_notification(
            event_type=NotificationEvent.TASK_ASSIGNED,
            recipients=[assigned_user],
            data={
                'title': '新任务分配',
                'message': f'您有新的任务: {task.task_name}',
                'task_id': task.id,
                'workorder_id': task.workorder.id,
                'workorder_number': task.workorder.order_number,
                'assigned_by': assigned_by.username if assigned_by else '系统'
            },
            priority=NotificationPriority.HIGH
        )
    
    def notify_workorder_approval(self, workorder, status, approved_by=None):
        """通知施工单审核结果"""
        recipients = [workorder.created_by]
        
        if status == 'approved':
            event_type = NotificationEvent.WORKORDER_APPROVED
            title = '施工单审核通过'
            message = f'您的施工单 {workorder.order_number} 已审核通过'
            priority = NotificationPriority.HIGH
        else:
            event_type = NotificationEvent.WORKORDER_REJECTED
            title = '施工单审核拒绝'
            message = f'您的施工单 {workorder.order_number} 已被拒绝'
            priority = NotificationPriority.URGENT
        
        self.send_notification(
            event_type=event_type,
            recipients=recipients,
            data={
                'title': title,
                'message': message,
                'workorder_id': workorder.id,
                'workorder_number': workorder.order_number,
                'approved_by': approved_by.username if approved_by else '系统',
                'status': status
            },
            priority=priority
        )
    
    def notify_process_completion(self, process, workorder, completed_by=None):
        """通知工序完成"""
        # 通知下一个工序的操作员
        next_process = self._get_next_process(workorder, process)
        recipients = []
        
        if next_process:
            # 获取下一个工序的操作员
            next_operators = self._get_process_operators(next_process)
            recipients.extend(next_operators)
        
        # 通知施工单创建者
        recipients.append(workorder.created_by)
        
        # 通知生产主管
        supervisors = self._get_supervisors()
        recipients.extend(supervisors)
        
        self.send_notification(
            event_type=NotificationEvent.PROCESS_COMPLETED,
            recipients=list(set(recipients)),  # 去重
            data={
                'title': '工序完成',
                'message': f'工序 {process.name} 已完成',
                'process_id': process.id,
                'process_name': process.name,
                'workorder_id': workorder.id,
                'workorder_number': workorder.order_number,
                'completed_by': completed_by.username if completed_by else '系统'
            },
            priority=NotificationPriority.NORMAL
        )
    
    def notify_deadline_warning(self, workorder, days_remaining):
        """通知交货期预警"""
        recipients = [workorder.created_by]
        
        # 添加相关操作员
        operators = self._get_workorder_operators(workorder)
        recipients.extend(operators)
        
        # 添加主管
        supervisors = self._get_supervisors()
        recipients.extend(supervisors)
        
        priority = NotificationPriority.URGENT if days_remaining <= 1 else NotificationPriority.HIGH
        
        self.send_notification(
            event_type=NotificationEvent.DEADLINE_WARNING,
            recipients=list(set(recipients)),
            data={
                'title': '交货期预警',
                'message': f'施工单 {workorder.order_number} 将在 {days_remaining} 天后到期',
                'workorder_id': workorder.id,
                'workorder_number': workorder.order_number,
                'deadline': workorder.deadline.strftime('%Y-%m-%d'),
                'days_remaining': days_remaining
            },
            priority=priority
        )
    
    def _get_next_process(self, workorder, current_process):
        """获取下一个工序"""
        try:
            from ..models.core import WorkOrderProcess, Process
            
            current_order = WorkOrderProcess.objects.get(
                workorder=workorder, 
                process=current_process
            ).order
            
            next_process = WorkOrderProcess.objects.filter(
                workorder=workorder,
                order=current_order + 1
            ).first()
            
            return next_process.process if next_process else None
            
        except Exception:
            return None
    
    def _get_process_operators(self, process):
        """获取工序操作员"""
        try:
            from ..models.system import UserProfile
            
            return User.objects.filter(
                userprofile__department=process.department,
                userprofile__is_active=True
            ).distinct()
        except Exception:
            return []
    
    def _get_workorder_operators(self, workorder):
        """获取施工单相关操作员"""
        try:
            from ..models.core import WorkOrderProcess, Process
            
            processes = WorkOrderProcess.objects.filter(workorder=workorder).values_list('process', flat=True)
            
            departments = Process.objects.filter(id__in=processes).values_list('department', flat=True)
            
            from ..models.system import UserProfile
            return User.objects.filter(
                userprofile__department__in=departments,
                userprofile__is_active=True
            ).distinct()
        except Exception:
            return []
    
    def _get_supervisors(self):
        """获取主管列表"""
        try:
            return User.objects.filter(
                groups__name='supervisor',
                is_active=True
            ).distinct()
        except Exception:
            return []


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket通知消费者"""
    
    async def connect(self):
        """建立WebSocket连接"""
        user = self.scope["user"]
        
        if user.is_authenticated:
            self.user_id = user.id
            self.group_name = f"user_{self.user_id}_notifications"
            
            # 加入用户通知组
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # 发送未读通知
            await self.send_unread_notifications()
        else:
            await self.close()
    
    async def disconnect(self, close_code):
        """断开WebSocket连接"""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def notification_message(self, event):
        """处理通知消息"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': event['notification']
        }))
    
    async def send_unread_notifications(self):
        """发送未读通知"""
        try:
            from ..models.system import Notification
            
            notifications = await sync_to_async(list)(
                Notification.objects.filter(
                    user_id=self.user_id,
                    is_read=False
                ).order_by('-created_at')[:20]
            )
            
            for notification in notifications:
                await self.send(text_data=json.dumps({
                    'type': 'notification',
                    'data': {
                        'event_type': notification.event_type,
                        'priority': notification.priority,
                        'title': notification.title,
                        'message': notification.message,
                        'data': notification.data,
                        'timestamp': notification.created_at.isoformat(),
                        'id': notification.id
                    }
                }))
                
                # 标记为已发送
                notification.is_sent = True
                await sync_to_async(notification.save)()
                
        except Exception as e:
            logger.error(f"发送未读通知失败: {e}")


class NotificationManager:
    """通知管理器"""
    
    @staticmethod
    def create_system_announcement(title: str, message: str, priority: str = NotificationPriority.NORMAL):
        """创建系统公告"""
        try:
            from ..models.system import UserProfile
            
            # 获取所有活跃用户
            active_users = User.objects.filter(
                userprofile__is_active=True,
                is_active=True
            ).distinct()
            
            notification_service = RealtimeNotificationService()
            notification_service.send_notification(
                event_type=NotificationEvent.SYSTEM_ANNOUNCEMENT,
                recipients=list(active_users),
                data={
                    'title': title,
                    'message': message,
                    'type': 'system_announcement'
                },
                priority=priority,
                channels=[NotificationChannel.WEBSOCKET, NotificationChannel.IN_APP]
            )
            
        except Exception as e:
            logger.error(f"创建系统公告失败: {e}")
    
    @staticmethod
    def send_urgent_order_alert(workorder):
        """发送紧急订单警报"""
        try:
            from ..models.system import UserProfile
            
            # 获取所有主管和操作员
            supervisors = User.objects.filter(groups__name='supervisor', is_active=True)
            
            # 获取相关操作员
            operators = RealtimeNotificationService()._get_workorder_operators(workorder)
            
            recipients = list(set(list(supervisors) + list(operators)))
            
            notification_service = RealtimeNotificationService()
            notification_service.send_notification(
                event_type=NotificationEvent.URGENT_ORDER,
                recipients=recipients,
                data={
                    'title': '紧急订单警报',
                    'message': f'紧急订单 {workorder.order_number} 需要立即处理',
                    'workorder_id': workorder.id,
                    'workorder_number': workorder.order_number,
                    'type': 'urgent_order'
                },
                priority=NotificationPriority.URGENT,
                channels=[NotificationChannel.WEBSOCKET, NotificationChannel.EMAIL, NotificationChannel.IN_APP]
            )
            
        except Exception as e:
            logger.error(f"发送紧急订单警报失败: {e}")


# 全局通知服务实例
notification_service = RealtimeNotificationService()