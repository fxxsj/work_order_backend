"""
通知系统测试管理命令

用于测试实时通知系统的各种功能
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from workorder.services.realtime_notification import (
    notification_service, NotificationManager, NotificationEvent, NotificationPriority
)
from workorder.models.core import WorkOrder
from workorder.models.system import Notification


class Command(BaseCommand):
    help = '测试实时通知系统'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['task', 'workorder', 'deadline', 'system', 'all'],
            default='all',
            help='测试通知类型'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='指定接收通知的用户ID'
        )
    
    def handle(self, *args, **options):
        test_type = options['type']
        user_id = options['user_id']
        
        self.stdout.write(self.style.SUCCESS('开始测试实时通知系统...'))
        
        if test_type in ['task', 'all']:
            self.test_task_notification(user_id)
        
        if test_type in ['workorder', 'all']:
            self.test_workorder_notification(user_id)
        
        if test_type in ['deadline', 'all']:
            self.test_deadline_notification(user_id)
        
        if test_type in ['system', 'all']:
            self.test_system_notification()
        
        # 显示统计信息
        self.show_notification_stats()
        
        self.stdout.write(self.style.SUCCESS('通知系统测试完成！'))
    
    def test_task_notification(self, user_id=None):
        """测试任务通知"""
        self.stdout.write('\n测试任务分配通知...')
        
        # 获取测试用户
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'用户ID {user_id} 不存在'))
                return
        else:
            user = User.objects.filter(is_active=True).first()
            if not user:
                self.stdout.write(self.style.ERROR('没有找到活跃用户'))
                return
        
        # 获取测试施工单
        workorder = WorkOrder.objects.filter(status='in_progress').first()
        if not workorder:
            self.stdout.write(self.style.WARNING('没有找到进行中的施工单'))
            return
        
        # 创建模拟任务
        from workorder.services.data_consistency import DataConsistencyService
        task_data = {
            'task_name': '测试任务通知',
            'process_name': '印刷',
            'assigned_to': user,
            'deadline': timezone.now() + timedelta(hours=24),
            'estimated_duration': 8
        }
        
        try:
            created_task = DataConsistencyService.create_task_safely(
                workorder, 
                task_data, 
                created_by=user
            )
            
            if created_task:
                notification_service.notify_task_assignment(
                    task=created_task,
                    assigned_user=user,
                    assigned_by=user
                )
                self.stdout.write(self.style.SUCCESS(f'✓ 任务分配通知已发送给 {user.username}'))
            else:
                self.stdout.write(self.style.WARNING('✗ 任务创建失败'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ 任务通知测试失败: {e}'))
    
    def test_workorder_notification(self, user_id=None):
        """测试施工单通知"""
        self.stdout.write('\n测试施工单审核通知...')
        
        # 获取待审核的施工单
        workorder = WorkOrder.objects.filter(approval_status='pending').first()
        if not workorder:
            self.stdout.write(self.style.WARNING('没有找到待审核的施工单'))
            return
        
        # 模拟审核通过
        notification_service.notify_workorder_approval(
            workorder=workorder,
            status='approved',
            approved_by=workorder.created_by
        )
        
        self.stdout.write(self.style.SUCCESS(f'✓ 施工单审核通知已发送给 {workorder.created_by.username}'))
    
    def test_deadline_notification(self, user_id=None):
        """测试交货期预警通知"""
        self.stdout.write('\n测试交货期预警通知...')
        
        # 查找即将到期的施工单
        tomorrow = timezone.now().date() + timedelta(days=1)
        workorder = WorkOrder.objects.filter(deadline=tomorrow).first()
        
        if not workorder:
            self.stdout.write(self.style.WARNING('没有找到即将到期的施工单，创建一个测试用例...'))
            
            # 创建测试用例
            creator = User.objects.filter(is_active=True).first()
            if creator:
                workorder = WorkOrder.objects.create(
                    order_number=f'TEST-{timezone.now().strftime("%Y%m%d%H%M%S")}',
                    customer=None,
                    total_amount=1000,
                    priority='normal',
                    deadline=tomorrow,
                    created_by=creator,
                    status='in_progress'
                )
            else:
                self.stdout.write(self.style.ERROR('没有找到用户创建测试施工单'))
                return
        
        notification_service.notify_deadline_warning(workorder, 1)
        self.stdout.write(self.style.SUCCESS(f'✓ 交货期预警通知已发送'))
    
    def test_system_notification(self):
        """测试系统公告通知"""
        self.stdout.write('\n测试系统公告通知...')
        
        NotificationManager.create_system_announcement(
            title='系统维护通知',
            message='系统将于今晚23:00-次日凌晨2:00进行维护升级，期间服务可能暂时无法访问，请提前做好准备。',
            priority=NotificationPriority.HIGH
        )
        
        self.stdout.write(self.style.SUCCESS('✓ 系统公告已发送给所有用户'))
    
    def show_notification_stats(self):
        """显示通知统计信息"""
        self.stdout.write('\n通知系统统计:')
        self.stdout.write('=' * 50)
        
        total_notifications = Notification.objects.count()
        unread_notifications = Notification.objects.filter(is_read=False).count()
        sent_notifications = Notification.objects.filter(is_sent=True).count()
        pending_notifications = Notification.objects.filter(is_sent=False).count()
        
        self.stdout.write(f'总通知数量: {total_notifications}')
        self.stdout.write(f'未读通知: {unread_notifications}')
        self.stdout.write(f'已发送通知: {sent_notifications}')
        self.stdout.write(f'待发送通知: {pending_notifications}')
        
        # 按优先级统计
        self.stdout.write('\n按优先级统计:')
        for priority, label in [
            (NotificationPriority.LOW, '低'),
            (NotificationPriority.NORMAL, '普通'),
            (NotificationPriority.HIGH, '高'),
            (NotificationPriority.URGENT, '紧急')
        ]:
            count = Notification.objects.filter(priority=priority).count()
            self.stdout.write(f'  {label}优先级: {count}')
        
        # 按事件类型统计
        self.stdout.write('\n按事件类型统计:')
        for event_type in [
            NotificationEvent.TASK_ASSIGNED,
            NotificationEvent.PROCESS_COMPLETED,
            NotificationEvent.WORKORDER_APPROVED,
            NotificationEvent.DEADLINE_WARNING,
            NotificationEvent.SYSTEM_ANNOUNCEMENT
        ]:
            count = Notification.objects.filter(event_type=event_type).count()
            if count > 0:
                self.stdout.write(f'  {event_type}: {count}')
        
        # 最近通知
        recent_notifications = Notification.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        self.stdout.write(f'\n最近1小时通知: {recent_notifications}')
        
        self.stdout.write('=' * 50)