"""
审计日志视图集

提供审计日志的查询、筛选、导出功能

Author: 小可 AI Assistant
Date: 2026-03-04
"""

import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.http import FileResponse

from ..models.audit import AuditLog, AuditLogExport, AuditLogSettings
from ..serializers.audit import AuditLogSerializer, AuditLogListSerializer, AuditLogExportSerializer, mask_sensitive_data
from .base_viewsets import ReadOnlyBaseViewSet

logger = logging.getLogger(__name__)


class AuditLogViewSet(ReadOnlyBaseViewSet):
    """
    审计日志视图集

    提供：
    - 列表查询（带筛选）
    - 详情查看
    - 按用户查询
    - 按对象查询
    - 导出功能
    - 统计功能
    """

    queryset = AuditLog.objects.all()
    serializer_class = None
    filterset_fields = ['action_type', 'user']
    search_fields = ['object_repr', 'username', 'ip_address']
    ordering_fields = ['created_at', 'action_type']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return AuditLogListSerializer
        return AuditLogSerializer

    def get_queryset(self):
        """
        优化查询集
        """
        queryset = super().get_queryset()

        # 自动优化查询
        queryset = queryset.select_related('user', 'content_type')

        # 时间范围过滤
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=start_date)
            except ValueError:
                pass

        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lte=end_date)
            except ValueError:
                pass

        # 模型过滤
        model = self.request.query_params.get('model')
        if model:
            queryset = queryset.filter(content_type__model=model)

        # 对象ID过滤
        object_id = self.request.query_params.get('object_id')
        if object_id:
            queryset = queryset.filter(object_id=object_id)

        # IP地址过滤
        ip_address = self.request.query_params.get('ip_address')
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)

        return queryset

    @action(detail=False, methods=['get'])
    def by_user(self, request):
        """
        按用户查询审计日志

        查询参数：
        - user_id: 用户ID（必填）
        - start_date: 开始日期（可选）
        - end_date: 结束日期（可选）
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({
                'code': 400,
                'message': '缺少 user_id 参数'
            }, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(user_id=user_id)

        # 分页
        page = self.paginate_queryset(queryset)
        if page is not None:
            from ..serializers.audit import AuditLogSerializer
            serializer = AuditLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_object(self, request):
        """
        按对象查询审计日志

        查询参数：
        - model: 模型名称（如 workorder）
        - object_id: 对象ID（必填）
        """
        model = request.query_params.get('model')
        object_id = request.query_params.get('object_id')

        if not object_id:
            return Response({
                'code': 400,
                'message': '缺少 object_id 参数'
            }, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(object_id=object_id)

        if model:
            queryset = queryset.filter(content_type__model=model)

        # 分页
        page = self.paginate_queryset(queryset)
        if page is not None:
            from ..serializers.audit import AuditLogSerializer
            serializer = AuditLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        审计日志统计

        返回：
        - 总操作数
        - 按操作类型统计
        - 按用户统计
        - 按日期统计
        """
        queryset = self.get_queryset()

        # 总操作数
        total_count = queryset.count()

        # 按操作类型统计
        action_type_stats = {}
        for action_type, _ in AuditLog.ACTION_CHOICES:
            count = queryset.filter(action_type=action_type).count()
            action_type_stats[action_type] = count

        # 按用户统计（前10）
        user_stats = {}
        for user_id, username in queryset.values_list('user__id', 'username').distinct()[:10]:
            if user_id:
                count = queryset.filter(user_id=user_id).count()
                user_stats[username] = count

        # 按日期统计（最近30天）
        date_stats = {}
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_logs = queryset.filter(created_at__gte=thirty_days_ago)

        for log in recent_logs:
            date = log.created_at.date().isoformat()
            date_stats[date] = date_stats.get(date, 0) + 1

        return Response({
            'code': 0,
            'message': 'success',
            'data': {
                'total_count': total_count,
                'action_type_stats': action_type_stats,
                'user_stats': user_stats,
                'date_stats': date_stats,
            }
        })

    @action(detail=False, methods=['post'])
    def export(self, request):
        """
        导出审计日志

        请求体：
        {
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "filters": {...}
        }

        返回：
        {
            "export_id": "uuid",
            "status": "pending"
        }
        """
        from ..services.audit_export_service import AuditExportService

        if not request.user.has_perm('workorder.add_auditlogexport') and not request.user.is_superuser:
            return Response({
                'code': 403,
                'message': '无导出权限'
            }, status=status.HTTP_403_FORBIDDEN)

        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        filters = request.data.get('filters', {})

        # 创建导出任务
        export_service = AuditExportService()
        export = export_service.create_export_task(
            user=request.user,
            start_date=start_date,
            end_date=end_date,
            filters=filters
        )
        export_service.trigger_export(export)

        return Response({
            'code': 0,
            'message': '导出任务已创建',
            'data': {
                'export_id': str(export.id),
                'status': export.status,
            }
        })

    @action(detail=True, methods=['get'])
    def diff(self, request, pk=None):
        """
        查看变更详情

        返回变更前后的数据对比
        """
        audit_log = self.get_object()

        if audit_log.action_type not in [AuditLog.ACTION_UPDATE, AuditLog.ACTION_CREATE, AuditLog.ACTION_DELETE]:
            return Response({
                'code': 400,
                'message': '只有创建、更新、删除操作有变更详情'
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'code': 0,
            'message': 'success',
            'data': {
                'id': str(audit_log.id),
                'action_type': audit_log.action_type,
                'object_repr': audit_log.object_repr,
                'changed_fields': audit_log.changed_fields,
                'changes': mask_sensitive_data(audit_log.changes),
                'user': audit_log.username,
                'created_at': audit_log.created_at.isoformat(),
            }
        })

    @action(detail=False, methods=['get'], url_path='exports')
    def export_list(self, request):
        if not request.user.has_perm('workorder.view_auditlogexport') and not request.user.is_superuser:
            return Response({
                'code': 403,
                'message': '无查看导出记录权限'
            }, status=status.HTTP_403_FORBIDDEN)

        queryset = AuditLogExport.objects.all().select_related('user').order_by('-created_at')

        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        user_id = request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=start_date)
            except ValueError:
                pass
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lte=end_date)
            except ValueError:
                pass

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = AuditLogExportSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = AuditLogExportSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path=r'exports/(?P<export_id>[^/.]+)/download')
    def export_download(self, request, export_id=None):
        if not request.user.has_perm('workorder.view_auditlogexport') and not request.user.is_superuser:
            return Response({
                'code': 403,
                'message': '无下载导出文件权限'
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            export = AuditLogExport.objects.get(id=export_id)
        except AuditLogExport.DoesNotExist:
            return Response({
                'code': 404,
                'message': '导出记录不存在'
            }, status=status.HTTP_404_NOT_FOUND)

        if export.status != AuditLogExport.STATUS_COMPLETED or not export.file_path:
            return Response({
                'code': 400,
                'message': '导出文件尚未就绪'
            }, status=status.HTTP_400_BAD_REQUEST)

        import os
        from django.conf import settings

        export_dir = getattr(settings, 'AUDIT_LOG_EXPORT_DIR', '/tmp/audit_logs')
        export_dir = os.path.abspath(export_dir)
        file_path = os.path.abspath(export.file_path)

        if not file_path.startswith(export_dir + os.sep):
            return Response({
                'code': 400,
                'message': '非法文件路径'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not os.path.exists(file_path):
            return Response({
                'code': 404,
                'message': '导出文件不存在'
            }, status=status.HTTP_404_NOT_FOUND)

        filename = os.path.basename(file_path)
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
