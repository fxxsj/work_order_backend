"""
审计日志管理命令

提供审计日志的管理和维护功能

Author: 小可 AI Assistant
Date: 2026-03-04
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from workorder.models.audit import AuditLog, AuditLogSettings


class Command(BaseCommand):
    help = '审计日志管理命令'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            dest='cleanup',
            help='清理过期的审计日志'
        )

        parser.add_argument(
            '--stats',
            action='store_true',
            dest='stats',
            help='显示审计日志统计信息'
        )

        parser.add_argument(
            '--enable',
            action='store_true',
            dest='enable',
            help='启用审计日志'
        )

        parser.add_argument(
            '--disable',
            action='store_true',
            dest='disable',
            help='禁用审计日志'
        )

        parser.add_argument(
            '--days',
            type=int,
            dest='days',
            help='设置日志保留天数'
        )
        parser.add_argument(
            '--process-exports',
            action='store_true',
            dest='process_exports',
            help='处理待导出的审计日志任务'
        )
        parser.add_argument(
            '--limit',
            type=int,
            dest='limit',
            default=10,
            help='处理导出任务数量（默认10）'
        )

    def handle(self, *args, **options):
        if options['cleanup']:
            self.cleanup_logs()

        if options['stats']:
            self.show_stats()

        if options['enable']:
            self.toggle_audit_log(True)

        if options['disable']:
            self.toggle_audit_log(False)

        if options['days']:
            self.set_retention_days(options['days'])

        if options['process_exports']:
            self.process_exports(limit=options.get('limit') or 10)

    def cleanup_logs(self):
        """清理过期的审计日志"""
        settings = AuditLogSettings.get_settings()
        retention_days = settings.retention_days

        cutoff_date = timezone.now() - timedelta(days=retention_days)

        # 删除过期日志
        deleted_count, _ = AuditLog.objects.filter(created_at__lt=cutoff_date).delete()

        self.stdout.write(
            self.style.SUCCESS(f'✓ 已清理 {deleted_count} 条过期日志（保留期: {retention_days}天）')
        )

    def show_stats(self):
        """显示审计日志统计信息"""
        total_count = AuditLog.objects.count()

        # 按操作类型统计
        action_stats = {}
        for action_type, _ in AuditLog.ACTION_CHOICES:
            count = AuditLog.objects.filter(action_type=action_type).count()
            action_stats[action_type] = count

        # 最早和最新的日志
        oldest_log = AuditLog.objects.order_by('created_at').first()
        newest_log = AuditLog.objects.order_by('-created_at').first()

        self.stdout.write(self.style.SUCCESS('=== 审计日志统计 ==='))
        self.stdout.write(f'总日志数: {total_count}')
        self.stdout.write(f'\n按操作类型统计:')
        for action_type, count in action_stats.items():
            self.stdout.write(f'  - {action_type}: {count}')

        if oldest_log:
            self.stdout.write(f'\n最早日志: {oldest_log.created_at}')
        if newest_log:
            self.stdout.write(f'最新日志: {newest_log.created_at}')

        # 显示配置
        settings = AuditLogSettings.get_settings()
        self.stdout.write(f'\n配置:')
        self.stdout.write(f'  - 状态: {"启用" if settings.enabled else "禁用"}')
        self.stdout.write(f'  - 保留期: {settings.retention_days}天')

    def toggle_audit_log(self, enable):
        """启用/禁用审计日志"""
        settings = AuditLogSettings.get_settings()
        settings.enabled = enable
        settings.save()

        status = "启用" if enable else "禁用"
        self.stdout.write(
            self.style.SUCCESS(f'✓ 审计日志已{status}')
        )

    def set_retention_days(self, days):
        """设置日志保留天数"""
        settings = AuditLogSettings.get_settings()
        settings.retention_days = days
        settings.save()

        self.stdout.write(
            self.style.SUCCESS(f'✓ 日志保留期已设置为 {days} 天')
        )

    def process_exports(self, limit=10):
        """处理待导出任务"""
        from workorder.services.audit_export_service import AuditExportService

        service = AuditExportService()
        service.process_pending_exports(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(f'✓ 已处理导出任务（最多 {limit} 条）')
        )
