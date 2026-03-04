"""
审计日志信号处理器

自动捕获 Django 模型的变更并记录到审计日志

使用方法：
1. 在 apps.py 中注册信号
2. 在需要审计的模型上添加审计混入类

Author: 小可 AI Assistant
Date: 2026-03-04
"""

import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.db.models import Model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from ..models.audit import AuditLog, AuditLogSettings, AuditMixin
from ..middleware.audit_log import get_current_request, get_client_ip as middleware_get_client_ip

logger = logging.getLogger(__name__)


def get_request_context():
    """
    获取当前请求上下文

    Returns:
        dict: 包含 user, ip_address, user_agent 等信息
    """
    request = get_current_request()
    if request:
        return {
            'user': getattr(request, 'user', None),
            'ip_address': middleware_get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'request_method': request.method,
            'request_path': request.path,
        }

    return {}


def get_client_ip(request):
    return middleware_get_client_ip(request)


def capture_changes(instance, created=False):
    """
    捕获模型变更

    Args:
        instance: 模型实例
        created: 是否为新建操作
    """
    # 检查审计日志是否启用
    settings = AuditLogSettings.get_settings()
    if not settings.enabled:
        return

    # 检查是否在审计模型列表中
    model_label = instance._meta.label_lower
    audited_models = {
        str(item).lower()
        for item in (settings.audited_models or [])
    }
    if audited_models:
        if model_label not in audited_models and instance._meta.label.lower() not in audited_models:
            return
        return

    try:
        # 获取请求上下文
        context = get_request_context()
        user = context.get('user')

        # 获取 Content Type
        content_type = ContentType.objects.get_for_model(instance)

        # 获取对象ID和表示
        object_id = str(instance.pk)
        object_repr = get_object_repr(instance)

        # 确定操作类型
        if created:
            action_type = AuditLog.ACTION_CREATE
            changes = {'new': model_to_dict(instance, settings=settings)}
            changed_fields = list(changes['new'].keys())
        else:
            action_type = AuditLog.ACTION_UPDATE
            old_data = getattr(instance, '_audit_old_data', None)
            changes, changed_fields = get_model_changes(
                instance,
                settings=settings,
                old_data=old_data,
            )

            # 如果没有变更，不记录
            if not changed_fields:
                return

        # 创建审计日志
        audit_log = AuditLog.objects.create(
            action_type=action_type,
            user=user,
            content_type=content_type,
            object_id=object_id,
            object_repr=object_repr,
            changes=changes,
            changed_fields=changed_fields,
            ip_address=context.get('ip_address'),
            user_agent=context.get('user_agent'),
            request_method=context.get('request_method'),
            request_path=context.get('request_path'),
        )

        logger.info(f"审计日志已创建: {audit_log}")

    except Exception as exc:
        logger.error(f"创建审计日志失败: {exc}", exc_info=True)


def model_to_dict(instance, settings=None):
    """
    将模型实例转换为字典

    Args:
        instance: 模型实例

    Returns:
        dict: 模型数据字典
    """
    from django.forms.models import model_to_dict as django_model_to_dict

    # 排除不需要审计的字段
    excluded_fields = {'last_login', 'updated_at', 'created_at'}
    if settings:
        excluded_fields.update(settings.excluded_fields or [])
    data = django_model_to_dict(instance, exclude=list(excluded_fields))

    # 添加多对多字段
    for field in instance._meta.many_to_many:
        if field.name not in excluded_fields:
            try:
                data[field.name] = list(getattr(instance, field.name).values_list('pk', flat=True))
            except Exception:
                pass

    return data


def get_model_changes(instance, settings=None, old_data=None):
    """
    获取模型的变更数据

    Args:
        instance: 模型实例

    Returns:
        tuple: (changes_dict, changed_fields_list)
    """
    if old_data is None:
        # 从数据库获取原始数据
        try:
            original = instance.__class__.objects.get(pk=instance.pk)
        except instance.__class__.DoesNotExist:
            return {}, []

        old_data = model_to_dict(original, settings=settings)
    new_data = model_to_dict(instance, settings=settings)

    # 找出变更的字段
    changed_fields = []
    changes = {'old': {}, 'new': {}}

    for field in old_data.keys():
        if old_data[field] != new_data[field]:
            changed_fields.append(field)
            changes['old'][field] = old_data[field]
            changes['new'][field] = new_data[field]

    return changes, changed_fields


def audit_log_save(sender, instance, created, **kwargs):
    """
    post_save 信号处理器

    自动记录模型的创建和更新操作
    """
    # 只审计继承自 AuditMixin 的模型
    if not isinstance(instance, AuditMixin):
        return

    # 排除 AuditLog 自身
    if sender == AuditLog:
        return

    capture_changes(instance, created=created)

    # 清理缓存的旧数据，避免长生命周期对象持有
    if hasattr(instance, '_audit_old_data'):
        delattr(instance, '_audit_old_data')


def audit_log_pre_save(sender, instance, **kwargs):
    """
    pre_save 信号处理器

    保存更新前的数据快照，供 post_save 对比
    """
    # 只审计继承自 AuditMixin 的模型
    if not isinstance(instance, AuditMixin):
        return

    # 排除 AuditLog 自身
    if sender == AuditLog:
        return

    # 新建时不需要缓存
    if not instance.pk:
        return

    # 检查审计日志是否启用
    settings = AuditLogSettings.get_settings()
    if not settings.enabled:
        return

    # 检查是否在审计模型列表中
    model_label = instance._meta.label_lower
    audited_models = {
        str(item).lower()
        for item in (settings.audited_models or [])
    }
    if audited_models:
        if model_label not in audited_models and instance._meta.label.lower() not in audited_models:
            return

    try:
        original = instance.__class__.objects.get(pk=instance.pk)
        instance._audit_old_data = model_to_dict(original, settings=settings)
    except instance.__class__.DoesNotExist:
        instance._audit_old_data = None


def audit_log_delete(sender, instance, **kwargs):
    """
    post_delete 信号处理器

    自动记录模型的删除操作
    """
    # 只审计继承自 AuditMixin 的模型
    if not isinstance(instance, AuditMixin):
        return

    # 排除 AuditLog 自身
    if sender == AuditLog:
        return

    # 检查审计日志是否启用
    settings = AuditLogSettings.get_settings()
    if not settings.enabled:
        return

    # 检查是否在审计模型列表中
    model_label = instance._meta.label_lower
    audited_models = {
        str(item).lower()
        for item in (settings.audited_models or [])
    }
    if audited_models:
        if model_label not in audited_models and instance._meta.label.lower() not in audited_models:
            return
        return

    try:
        # 获取请求上下文
        context = get_request_context()
        user = context.get('user')

        # 获取 Content Type
        content_type = ContentType.objects.get_for_model(instance)

        # 获取对象ID和表示
        object_id = str(instance.pk)
        object_repr = get_object_repr(instance)

        # 记录删除前的数据
        changes = {'old': model_to_dict(instance, settings=settings)}

        # 创建审计日志
        audit_log = AuditLog.objects.create(
            action_type=AuditLog.ACTION_DELETE,
            user=user,
            content_type=content_type,
            object_id=object_id,
            object_repr=object_repr,
            changes=changes,
            changed_fields=list(changes['old'].keys()),
            ip_address=context.get('ip_address'),
            user_agent=context.get('user_agent'),
            request_method=context.get('request_method'),
            request_path=context.get('request_path'),
        )

        logger.info(f"删除审计日志已创建: {audit_log}")

    except Exception as exc:
        logger.error(f"创建删除审计日志失败: {exc}", exc_info=True)


def register_audit_signals(sender, **kwargs):
    """
    注册审计信号

    在 apps.py 的 ready() 方法中调用
    """
    # 注册所有继承自 AuditMixin 的模型
    for model in sender.get_models():
        if issubclass(model, AuditMixin):
            pre_save.connect(audit_log_pre_save, sender=model, weak=False)
            post_save.connect(audit_log_save, sender=model, weak=False)
            post_delete.connect(audit_log_delete, sender=model, weak=False)
            logger.info(f"已注册审计信号: {model._meta.label}")


def get_object_repr(instance):
    """
    获取对象的审计显示内容
    """
    if hasattr(instance, 'get_audit_log_repr'):
        return instance.get_audit_log_repr()
    return str(instance)
