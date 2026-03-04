"""
审计日志导出服务

提供审计日志的导出功能，支持异步导出大文件

Author: 小可 AI Assistant
Date: 2026-03-04
"""

import logging
import csv
import os
from datetime import datetime
from django.conf import settings
from django.utils import timezone

from ..models.audit import AuditLog, AuditLogExport

logger = logging.getLogger(__name__)


class AuditExportService:
    """
    审计日志导出服务
    """

    def create_export_task(self, user, start_date, end_date, filters=None):
        """
        创建导出任务

        Args:
            user: 用户对象
            start_date: 开始日期
            end_date: 结束日期
            filters: 过滤条件

        Returns:
            AuditLogExport: 导出任务对象
        """
        export = AuditLogExport.objects.create(
            user=user,
            start_date=start_date,
            end_date=end_date,
            filters=filters or {},
            status=AuditLogExport.STATUS_PENDING
        )

        return export

    def trigger_export(self, export):
        """
        触发导出任务
        - async_write=True: 仅创建任务，等待定时器/队列处理
        - async_write=False: 同步执行
        """
        from ..models.audit import AuditLogSettings

        settings_obj = AuditLogSettings.get_settings()
        if not settings_obj.async_write:
            self.perform_export(export.id)
            return
        # 异步模式下，由定时任务或队列处理 pending 导出

    def perform_export(self, export_id):
        """
        执行导出任务

        Args:
            export_id: 导出任务ID
        """
        export = AuditLogExport.objects.get(id=export_id)
        if export.status not in [AuditLogExport.STATUS_PENDING, AuditLogExport.STATUS_FAILED]:
            return
        export.status = AuditLogExport.STATUS_PROCESSING
        export.save()

        try:
            # 构建查询
            queryset = AuditLog.objects.all()

            # 时间范围
            if export.start_date:
                queryset = queryset.filter(created_at__gte=export.start_date)
            if export.end_date:
                queryset = queryset.filter(created_at__lte=export.end_date)

            # 应用过滤条件
            filters = export.filters
            if filters.get('action_type'):
                queryset = queryset.filter(action_type=filters['action_type'])
            if filters.get('user_id'):
                queryset = queryset.filter(user_id=filters['user_id'])
            if filters.get('model'):
                queryset = queryset.filter(content_type__model=filters['model'])

            # 统计
            export.record_count = queryset.count()

            # 生成文件路径
            filename = f"audit_log_{export.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
            export_dir = getattr(settings, 'AUDIT_LOG_EXPORT_DIR', '/tmp/audit_logs')
            os.makedirs(export_dir, exist_ok=True)
            file_path = os.path.join(export_dir, filename)

            # 导出为CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # 写入表头
                writer.writerow([
                    'ID',
                    '操作类型',
                    '用户',
                    '对象类型',
                    '对象ID',
                    '对象表示',
                    '变更字段',
                    'IP地址',
                    '创建时间',
                ])

                # 写入数据
                for log in queryset:
                    writer.writerow([
                        str(log.id),
                        log.get_action_type_display(),
                        log.username,
                        log.content_type.model if log.content_type else '',
                        log.object_id,
                        log.object_repr,
                        ','.join(log.changed_fields),
                        log.ip_address or '',
                        log.created_at.isoformat(),
                    ])

            # 获取文件大小
            export.file_size = os.path.getsize(file_path)
            export.file_path = file_path
            export.status = AuditLogExport.STATUS_COMPLETED
            export.completed_at = timezone.now()
            export.save()

            logger.info(f"审计日志导出完成: {export_id}, 记录数: {export.record_count}")

        except Exception as exc:
            export.status = AuditLogExport.STATUS_FAILED
            export.error_message = str(exc)
            export.completed_at = timezone.now()
            export.save()

            logger.error(f"审计日志导出失败: {export_id}, 错误: {exc}", exc_info=True)

    def process_pending_exports(self, limit=10):
        """
        处理待导出的任务
        """
        pending_exports = (
            AuditLogExport.objects
            .filter(status=AuditLogExport.STATUS_PENDING)
            .order_by('created_at')[:limit]
        )

        for export in pending_exports:
            self.perform_export(export.id)
