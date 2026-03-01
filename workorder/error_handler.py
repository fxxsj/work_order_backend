"""
统一错误处理

提供标准化的错误响应格式，改善前端错误处理体验。
"""

import logging
import traceback
from rest_framework.views import exception_handler
from django.utils import timezone
from django.conf import settings
from workorder.response import APIResponse

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    自定义异常处理器

    提供统一的错误响应格式，包括错误代码、消息、详细信息等。

    Args:
        exc: 异常实例
        context: 请求上下文

    Returns:
        Response: 标准化的错误响应
    """
    # 首先调用 DRF 的默认异常处理器
    response = exception_handler(exc, context)

    if response is not None:
        # DRF 异常（如 APIException）
        message = str(exc.detail) if hasattr(exc, 'detail') else str(exc)
        code = getattr(exc, 'default_code', 'error')
        custom_response_data = {
            'success': False,
            'code': response.status_code,
            'message': message,
            'errors': {
                'code': code,
            },
            'data': None,
            'timestamp': timezone.now().isoformat(),
        }

        # 如果有详细信息，添加到响应中
        if hasattr(response.data, 'items'):
            details = {}
            for key, value in response.data.items():
                if isinstance(value, list):
                    details[key] = value
                elif isinstance(value, str):
                    details[key] = [value]
                else:
                    details[key] = [str(value)]

            if details:
                custom_response_data['errors']['details'] = details

        response.data = custom_response_data

        # 记录错误日志
        logger.error(
            f"API Error: {custom_response_data['errors']['code']} - "
            f"{custom_response_data['message']}",
            extra={
                'status_code': response.status_code,
                'path': context['request'].path,
                'method': context['request'].method,
            }
        )

    else:
        # 非 DRF 异常（如 Python 标准异常）
        # 在生产环境中，不应该暴露详细的错误信息
        if settings.DEBUG:
            # 开发环境：显示详细错误信息
            error_message = str(exc)
            error_details = traceback.format_exc()
        else:
            # 生产环境：显示通用错误信息
            error_message = '服务器内部错误'
            error_details = None

        response_data = {
            'success': False,
            'code': 500,
            'message': error_message,
            'errors': {
                'code': 'INTERNAL_ERROR',
            },
            'data': None,
            'timestamp': timezone.now().isoformat(),
        }

        if error_details:
            response_data['errors']['debug'] = error_details

        response = APIResponse.error(
            message=error_message,
            code=500,
            errors=response_data['errors'],
            data=None,
        )

        # 记录未捕获的异常
        logger.exception(
            f"Unhandled Exception: {exc}",
            extra={
                'path': context['request'].path,
                'method': context['request'].method,
            }
        )

    return response


class ErrorHandler:
    """
    错误处理器工具类

    提供便捷的错误处理方法。
    """

    @staticmethod
    def validation_error(message, details=None):
        """
        创建验证错误响应

        Args:
            message: 错误消息
            details: 详细错误信息字典

        Returns:
            Response: 错误响应
        """
        errors = {'code': 'VALIDATION_ERROR'}
        if details:
            errors['details'] = details
        return APIResponse.error(message=message, code=400, errors=errors, data=None)

    @staticmethod
    def permission_denied(message='权限不足'):
        """
        创建权限拒绝响应

        Args:
            message: 错误消息

        Returns:
            Response: 错误响应
        """
        return APIResponse.error(
            message=message,
            code=403,
            errors={'code': 'PERMISSION_DENIED'},
            data=None,
        )

    @staticmethod
    def not_found(message='资源未找到'):
        """
        创建资源未找到响应

        Args:
            message: 错误消息

        Returns:
            Response: 错误响应
        """
        return APIResponse.error(
            message=message,
            code=404,
            errors={'code': 'NOT_FOUND'},
            data=None,
        )

    @staticmethod
    def business_logic_error(message, details=None):
        """
        创建业务逻辑错误响应

        Args:
            message: 错误消息
            details: 详细错误信息字典

        Returns:
            Response: 错误响应
        """
        errors = {'code': 'BUSINESS_LOGIC_ERROR'}
        if details:
            errors['details'] = details
        return APIResponse.error(
            message=message,
            code=422,
            errors=errors,
            data=None,
        )
