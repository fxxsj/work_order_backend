"""
审计日志序列化器

Author: 小可 AI Assistant
Date: 2026-03-04
"""

from rest_framework import serializers
from ..models.audit import AuditLog, AuditLogExport, AuditLogSettings


def mask_sensitive_data(input_data):
    sensitive_keys = [
        'password',
        'token',
        'secret',
        'csrf',
        'api_key',
        'access',
        'refresh',
    ]

    def is_sensitive(key):
        if not key:
            return False
        normalized = str(key).lower()
        return any(item in normalized for item in sensitive_keys)

    def walk(value):
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, dict):
            result = {}
            for key, val in value.items():
                result[key] = '***' if is_sensitive(key) else walk(val)
            return result
        return value

    return walk(input_data)


class AuditLogSerializer(serializers.ModelSerializer):
    """
    审计日志序列化器
    """

    username = serializers.CharField(read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'action_type',
            'user',
            'username',
            'user_email',
            'content_type',
            'content_type_name',
            'object_id',
            'object_repr',
            'changes',
            'changed_fields',
            'ip_address',
            'user_agent',
            'request_method',
            'request_path',
            'extra_context',
            'created_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('changes'):
            data['changes'] = mask_sensitive_data(data['changes'])
        if data.get('extra_context'):
            data['extra_context'] = mask_sensitive_data(data['extra_context'])
        return data


class AuditLogListSerializer(serializers.ModelSerializer):
    """
    审计日志列表序列化器（简化版）
    """

    username = serializers.CharField(read_only=True)
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'action_type',
            'username',
            'content_type_name',
            'object_repr',
            'changed_fields',
            'ip_address',
            'created_at',
        ]


class AuditLogDetailSerializer(AuditLogSerializer):
    """
    审计日志详情序列化器（包含完整变更数据）
    """

    class Meta(AuditLogSerializer.Meta):
        model = AuditLog
        fields = AuditLogSerializer.Meta.fields


class AuditLogExportSerializer(serializers.ModelSerializer):
    """
    审计日志导出序列化器
    """

    username = serializers.CharField(source='user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AuditLogExport
        fields = [
            'id',
            'user',
            'username',
            'start_date',
            'end_date',
            'filters',
            'file_path',
            'record_count',
            'file_size',
            'status',
            'status_display',
            'error_message',
            'created_at',
            'completed_at',
        ]
        read_only_fields = fields


class AuditLogSettingsSerializer(serializers.ModelSerializer):
    """
    审计日志配置序列化器
    """

    class Meta:
        model = AuditLogSettings
        fields = [
            'retention_days',
            'enabled',
            'log_login',
            'log_logout',
            'log_export',
            'log_import',
            'async_write',
            'audited_models',
            'excluded_fields',
            'updated_at',
        ]
