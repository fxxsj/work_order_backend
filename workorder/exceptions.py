"""
自定义异常类

定义应用程序特定的异常类型，提供更清晰的错误处理。
"""

from rest_framework.exceptions import APIException
from django.utils.translation import gettext_lazy as _


class ValidationError(APIException):
    """
    验证错误

    用于请求数据验证失败的情况。
    """

    status_code = 400
    default_detail = _('验证失败')
    default_code = 'validation_error'


class BusinessLogicError(APIException):
    """
    业务逻辑错误

    用于业务规则验证失败的情况。
    """

    status_code = 422
    default_detail = _('业务逻辑错误')
    default_code = 'business_logic_error'


class PermissionDeniedError(APIException):
    """
    权限错误

    用于用户权限不足的情况。
    """

    status_code = 403
    default_detail = _('权限不足')
    default_code = 'permission_denied'


class ResourceNotFoundError(APIException):
    """
    资源未找到错误

    用于请求的资源不存在的情况。
    """

    status_code = 404
    default_detail = _('资源未找到')
    default_code = 'resource_not_found'


class ConflictError(APIException):
    """
    冲突错误

    用于请求与资源当前状态冲突的情况。
    """

    status_code = 409
    default_detail = _('资源冲突')
    default_code = 'conflict_error'


class TaskConflictError(ConflictError):
    """
    任务冲突错误

    用于任务分配/认领时的并发冲突检测。
    当两个用户同时尝试分配或认领同一任务时抛出。
    """

    status_code = 409
    default_detail = _('该任务正在被其他用户操作，请刷新后重试')
    default_code = 'task_conflict'

    def __init__(self, detail=None, current_owner=None, task_id=None):
        """
        Args:
            detail: 错误详情
            current_owner: 当前任务拥有者信息
            task_id: 任务ID
        """
        if detail is None:
            detail = self.default_detail
        super().__init__(detail)
        self.current_owner = current_owner
        self.task_id = task_id

    def __str__(self):
        if self.current_owner:
            return f"任务冲突：该任务已被 {self.current_owner} 分配"
        return str(self.default_detail)


class RateLimitError(APIException):
    """
    速率限制错误

    用于请求超过速率限制的情况。
    """

    status_code = 429
    default_detail = _('请求过于频繁，请稍后再试')
    default_code = 'rate_limit_error'


class ServiceUnavailableError(APIException):
    """
    服务不可用错误

    用于服务暂时不可用的情况。
    """

    status_code = 503
    default_detail = _('服务暂时不可用，请稍后再试')
    default_code = 'service_unavailable'
