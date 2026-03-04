"""
审计日志模型

记录系统中所有重要操作的完整审计追踪，包括：
- 数据变更（创建、更新、删除）
- 操作者信息
- 变更前后数据
- 请求上下文（IP、User-Agent）

Author: 小可 AI Assistant
Date: 2026-03-04
"""

import uuid
import json
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone


class AuditLog(models.Model):
    """
    审计日志主模型

    记录所有重要的数据变更操作，用于：
    - 安全审计
    - 问题排查
    - 合规要求（ISO、SOC2）
    - 数据恢复
    """

    # ========== 操作类型 ==========
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_VIEW = 'view'
    ACTION_EXPORT = 'export'
    ACTION_IMPORT = 'import'
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'
    ACTION_LOGIN = 'login'
    ACTION_LOGOUT = 'logout'

    ACTION_CHOICES = [
        (ACTION_CREATE, '创建'),
        (ACTION_UPDATE, '更新'),
        (ACTION_DELETE, '删除'),
        (ACTION_VIEW, '查看'),
        (ACTION_EXPORT, '导出'),
        (ACTION_IMPORT, '导入'),
        (ACTION_APPROVE, '审核通过'),
        (ACTION_REJECT, '审核拒绝'),
        (ACTION_LOGIN, '登录'),
        (ACTION_LOGOUT, '登出'),
    ]

    # ========== 字段定义 ==========
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='日志ID'
    )

    # 操作信息
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        db_index=True,
        verbose_name='操作类型'
    )

    # 操作者（可为空，如系统任务）
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        db_index=True,
        verbose_name='操作用户'
    )

    # 用户名快照（防止用户被删除后丢失信息）
    username = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='用户名快照'
    )

    # 对象信息（Generic Foreign Key）
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='内容类型'
    )

    object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='对象ID'
    )

    object_repr = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='对象表示'
    )

    content_object = GenericForeignKey('content_type', 'object_id')

    # 变更数据
    changes = models.JSONField(
        default=dict,
        verbose_name='变更数据',
        help_text='记录变更前后的数据对比'
    )

    # 变更字段列表
    changed_fields = models.JSONField(
        default=list,
        verbose_name='变更字段'
    )

    # 请求上下文
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP地址'
    )

    user_agent = models.TextField(
        blank=True,
        verbose_name='用户代理'
    )

    request_method = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='请求方法'
    )

    request_path = models.TextField(
        blank=True,
        verbose_name='请求路径'
    )

    # 额外上下文
    extra_context = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='额外上下文',
        help_text='存储额外的上下文信息，如业务逻辑相关数据'
    )

    # 时间戳
    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name='创建时间'
    )

    # 元数据
    class Meta:
        db_table = 'audit_log'
        verbose_name = '审计日志'
        verbose_name_plural = '审计日志'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['action_type', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.get_action_type_display()} - {self.object_repr} by {self.username}"

    def save(self, *args, **kwargs):
        # 保存用户名快照
        if self.user:
            self.username = self.user.username
        super().save(*args, **kwargs)


class AuditMixin(models.Model):
    """
    审计混入类

    将此混入类添加到需要审计的模型中，自动启用审计功能
    """

    def get_audit_log_repr(self):
        """
        获取对象的审计日志表示

        Returns:
            str: 对象的字符串表示
        """
        return str(self)

    class Meta:
        abstract = True


class AuditLogExport(models.Model):
    """
    审计日志导出记录

    记录审计日志的导出操作，防止滥用
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # 导出者
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_log_exports'
    )

    # 导出范围
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    filters = models.JSONField(default=dict, help_text='导出时使用的过滤条件')

    # 导出结果
    file_path = models.CharField(max_length=512, blank=True)
    record_count = models.IntegerField(default=0)
    file_size = models.IntegerField(default=0, help_text='文件大小（字节）')

    # 状态
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待处理'),
        (STATUS_PROCESSING, '处理中'),
        (STATUS_COMPLETED, '已完成'),
        (STATUS_FAILED, '失败'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    error_message = models.TextField(blank=True)

    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'audit_log_export'
        verbose_name = '审计日志导出'
        verbose_name_plural = '审计日志导出'
        ordering = ['-created_at']

    def __str__(self):
        return f"导出 {self.start_date} ~ {self.end_date} by {self.user}"


class AuditLogSettings(models.Model):
    """
    审计日志配置

    系统级别的审计日志配置
    """

    # 日志保留期（天）
    retention_days = models.IntegerField(
        default=365,
        help_text='日志保留天数，超过此天数的日志将被自动清理'
    )

    # 是否启用审计日志
    enabled = models.BooleanField(
        default=True,
        help_text='是否启用审计日志功能'
    )

    # 敏感操作强制记录
    log_login = models.BooleanField(default=True, verbose_name='记录登录')
    log_logout = models.BooleanField(default=True, verbose_name='记录登出')
    log_export = models.BooleanField(default=True, verbose_name='记录导出')
    log_import = models.BooleanField(default=True, verbose_name='记录导入')

    # 异步写入
    async_write = models.BooleanField(
        default=True,
        help_text='异步写入日志，提高性能'
    )

    # 需要审计的模型
    audited_models = models.JSONField(
        default=list,
        help_text='需要审计的模型列表（格式：app.Model）'
    )

    # 不需要审计的字段
    excluded_fields = models.JSONField(
        default=list,
        help_text='不需要审计的字段列表（如：last_login）'
    )

    # 时间戳
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'audit_log_settings'
        verbose_name = '审计日志配置'
        verbose_name_plural = '审计日志配置'

    def __str__(self):
        return f"审计日志配置（保留{self.retention_days}天）"

    @classmethod
    def get_settings(cls):
        """获取当前配置（单例模式）"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
