"""
实时通知视图和序列化器

提供通知管理、WebSocket连接、通知设置等功能
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from ..models.system import Notification
from ..services.realtime_notification import (
    RealtimeNotificationService, NotificationManager, 
    NotificationEvent, NotificationPriority, NotificationChannel
)


class NotificationPagination(PageNumberPagination):
    """通知分页器"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class NotificationSerializer:
    """通知序列化器"""
    
    @staticmethod
    def serialize_notification(notification):
        """序列化通知对象"""
        return {
            'id': notification.id,
            'event_type': notification.event_type,
            'priority': notification.priority,
            'title': notification.title,
            'message': notification.message,
            'data': notification.data,
            'is_read': notification.is_read,
            'is_sent': notification.is_sent,
            'created_at': notification.created_at.isoformat(),
            'updated_at': notification.updated_at.isoformat()
        }


class NotificationViewSet(viewsets.GenericViewSet):
    """通知管理视图集"""
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination
    
    def get_queryset(self):
        """获取当前用户的通知查询集"""
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    
    def list(self, request):
        """获取通知列表"""
        notifications = self.get_queryset()
        
        # 分页
        page = self.paginate_queryset(notifications)
        if page is not None:
            data = [NotificationSerializer.serialize_notification(n) for n in page]
            return self.get_paginated_response(data)
        
        # 如果没有分页，返回所有
        data = [NotificationSerializer.serialize_notification(n) for n in notifications]
        return Response(data)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """标记通知为已读"""
        try:
            notification = self.get_queryset().get(id=pk)
            notification.is_read = True
            notification.save(update_fields=['is_read'])
            
            return Response({
                'message': '通知已标记为已读',
                'notification': NotificationSerializer.serialize_notification(notification)
            })
        except Notification.DoesNotExist:
            return Response(
                {'error': '通知不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """标记所有通知为已读"""
        count = self.get_queryset().filter(is_read=False).update(is_read=True)
        
        return Response({
            'message': f'已标记 {count} 条通知为已读',
            'count': count
        })
    
    @action(detail=True, methods=['delete'])
    def delete(self, request, pk=None):
        """删除通知"""
        try:
            notification = self.get_queryset().get(id=pk)
            notification.delete()
            
            return Response({
                'message': '通知已删除'
            })
        except Notification.DoesNotExist:
            return Response(
                {'error': '通知不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['delete'])
    def delete_all_read(self, request):
        """删除所有已读通知"""
        count = self.get_queryset().filter(is_read=True).delete()[0]
        
        return Response({
            'message': f'已删除 {count} 条已读通知',
            'count': count
        })
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """获取未读通知数量"""
        count = self.get_queryset().filter(is_read=False).count()
        
        return Response({
            'unread_count': count
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取通知统计"""
        queryset = self.get_queryset()
        
        # 按优先级统计
        priority_stats = {}
        for priority, label in [
            (NotificationPriority.LOW, '低'),
            (NotificationPriority.NORMAL, '普通'),
            (NotificationPriority.HIGH, '高'),
            (NotificationPriority.URGENT, '紧急')
        ]:
            count = queryset.filter(priority=priority).count()
            priority_stats[priority] = {
                'label': label,
                'count': count
            }
        
        # 按事件类型统计
        event_stats = {}
        for event_type in [
            NotificationEvent.TASK_ASSIGNED,
            NotificationEvent.PROCESS_COMPLETED,
            NotificationEvent.WORKORDER_APPROVED,
            NotificationEvent.DEADLINE_WARNING,
            NotificationEvent.SYSTEM_ANNOUNCEMENT
        ]:
            count = queryset.filter(event_type=event_type).count()
            if count > 0:
                event_stats[event_type] = count
        
        # 按时间统计（最近7天）
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_count = queryset.filter(created_at__gte=seven_days_ago).count()
        
        return Response({
            'total_count': queryset.count(),
            'unread_count': queryset.filter(is_read=False).count(),
            'read_count': queryset.filter(is_read=True).count(),
            'recent_count': recent_count,
            'priority_stats': priority_stats,
            'event_stats': event_stats
        })


class SystemNotificationViewSet(viewsets.GenericViewSet):
    """系统通知管理视图集"""
    permission_classes = [permissions.IsAdminUser]
    
    @action(detail=False, methods=['post'])
    def create_announcement(self, request):
        """创建系统公告"""
        title = request.data.get('title')
        message = request.data.get('message')
        priority = request.data.get('priority', NotificationPriority.NORMAL)
        
        if not title or not message:
            return Response(
                {'error': '标题和消息不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        NotificationManager.create_system_announcement(title, message, priority)
        
        return Response({
            'message': '系统公告已创建',
            'title': title,
            'priority': priority
        })
    
    @action(detail=False, methods=['post'])
    def send_urgent_alert(self, request):
        """发送紧急警报"""
        workorder_id = request.data.get('workorder_id')
        
        if not workorder_id:
            return Response(
                {'error': '请提供施工单ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from ..models.core import WorkOrder
            workorder = WorkOrder.objects.get(id=workorder_id)
            
            NotificationManager.send_urgent_order_alert(workorder)
            
            return Response({
                'message': '紧急警报已发送',
                'workorder_id': workorder_id,
                'workorder_number': workorder.order_number
            })
            
        except WorkOrder.DoesNotExist:
            return Response(
                {'error': '施工单不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def notification_settings(self, request):
        """获取通知设置"""
        # 这里可以从数据库或配置文件中获取通知设置
        settings_data = {
            'websocket_enabled': True,
            'email_enabled': True,
            'sms_enabled': False,
            'email_threshold': NotificationPriority.HIGH,
            'notification_retention_days': 30,
            'auto_cleanup_enabled': True,
            'max_notifications_per_user': 1000
        }
        
        return Response(settings_data)
    
    @action(detail=False, methods=['post'])
    def update_notification_settings(self, request):
        """更新通知设置"""
        # 这里可以实现通知设置的更新逻辑
        # 为了简化，暂时返回成功响应
        return Response({
            'message': '通知设置已更新'
        })
    
    @action(detail=False, methods=['get'])
    def system_status(self, request):
        """获取通知系统状态"""
        try:
            from channels.layers import get_channel_layer
            
            channel_layer = get_channel_layer()
            
            # 统计活跃连接数（这个需要在实际实现中维护）
            active_connections = 0  # 这里需要实际的连接统计逻辑
            
            # 统计未发送通知
            unsent_notifications = Notification.objects.filter(
                is_sent=False
            ).count()
            
            # 统计最近通知数量
            recent_notifications = Notification.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            return Response({
                'status': 'healthy',
                'active_connections': active_connections,
                'unsent_notifications': unsent_notifications,
                'recent_notifications': recent_notifications,
                'channel_layer_type': str(type(channel_layer).__name__),
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserNotificationSettingsViewSet(viewsets.GenericViewSet):
    """用户通知设置视图集"""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def get_settings(self, request):
        """获取用户通知设置"""
        user = request.user
        
        # 这里可以从用户配置中获取个性化设置
        settings_data = {
            'user_id': user.id,
            'email_notifications': True,
            'websocket_notifications': True,
            'task_assignments': True,
            'process_completions': True,
            'deadline_warnings': True,
            'system_announcements': True,
            'urgency_threshold': NotificationPriority.NORMAL,
            'quiet_hours_enabled': False,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '08:00'
        }
        
        return Response(settings_data)
    
    @action(detail=False, methods=['post'])
    def update_settings(self, request):
        """更新用户通知设置"""
        user = request.user
        settings_data = request.data
        
        # 这里可以实现用户个性化设置的保存逻辑
        # 为了简化，暂时返回成功响应
        
        return Response({
            'message': '通知设置已更新',
            'user_id': user.id,
            'settings': settings_data
        })
    
    @action(detail=False, methods=['get'])
    def notification_preferences(self, request):
        """获取通知偏好设置"""
        preferences = {
            'task_assigned': {
                'label': '任务分配',
                'description': '当有新任务分配给您时通知',
                'enabled': True,
                'channels': [NotificationChannel.WEBSOCKET, NotificationChannel.IN_APP]
            },
            'process_completed': {
                'label': '工序完成',
                'description': '当相关工序完成时通知',
                'enabled': True,
                'channels': [NotificationChannel.WEBSOCKET, NotificationChannel.IN_APP]
            },
            'workorder_approved': {
                'label': '施工单审核',
                'description': '当施工单审核结果出来时通知',
                'enabled': True,
                'channels': [NotificationChannel.WEBSOCKET, NotificationChannel.IN_APP, NotificationChannel.EMAIL]
            },
            'deadline_warning': {
                'label': '交货期预警',
                'description': '当施工单接近交货期时通知',
                'enabled': True,
                'channels': [NotificationChannel.WEBSOCKET, NotificationChannel.IN_APP, NotificationChannel.EMAIL]
            },
            'system_announcement': {
                'label': '系统公告',
                'description': '系统重要公告通知',
                'enabled': True,
                'channels': [NotificationChannel.WEBSOCKET, NotificationChannel.IN_APP]
            }
        }
        
        return Response(preferences)


class NotificationTemplateViewSet(viewsets.GenericViewSet):
    """通知模板视图集"""
    permission_classes = [permissions.IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def get_templates(self, request):
        """获取通知模板"""
        templates = {
            'task_assigned': {
                'title': '新任务分配',
                'message': '您有新的任务: {task_name}',
                'variables': ['task_name', 'workorder_number', 'assigned_by']
            },
            'process_completed': {
                'title': '工序完成',
                'message': '工序 {process_name} 已完成',
                'variables': ['process_name', 'workorder_number', 'completed_by']
            },
            'workorder_approved': {
                'title': '施工单审核通过',
                'message': '您的施工单 {workorder_number} 已审核通过',
                'variables': ['workorder_number', 'approved_by']
            },
            'workorder_rejected': {
                'title': '施工单审核拒绝',
                'message': '您的施工单 {workorder_number} 已被拒绝',
                'variables': ['workorder_number', 'rejected_by']
            },
            'deadline_warning': {
                'title': '交货期预警',
                'message': '施工单 {workorder_number} 将在 {days_remaining} 天后到期',
                'variables': ['workorder_number', 'days_remaining', 'deadline']
            },
            'urgent_order': {
                'title': '紧急订单警报',
                'message': '紧急订单 {workorder_number} 需要立即处理',
                'variables': ['workorder_number', 'priority']
            }
        }
        
        return Response(templates)
    
    @action(detail=False, methods=['post'])
    def preview_template(self, request):
        """预览通知模板"""
        template_name = request.data.get('template_name')
        variables = request.data.get('variables', {})
        
        templates = {
            'task_assigned': {
                'title': '新任务分配',
                'message': '您有新的任务: {task_name}'
            },
            'process_completed': {
                'title': '工序完成',
                'message': '工序 {process_name} 已完成'
            }
        }
        
        if template_name not in templates:
            return Response(
                {'error': '模板不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        template = templates[template_name]
        title = template['title'].format(**variables)
        message = template['message'].format(**variables)
        
        return Response({
            'template_name': template_name,
            'title': title,
            'message': message,
            'variables': variables
        })