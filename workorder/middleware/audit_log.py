"""
审计日志中间件

捕获请求上下文信息，供信号处理器使用

Author: 小可 AI Assistant
Date: 2026-03-04
"""

import logging
from threading import local

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# 线程本地存储
_thread_locals = local()


class AuditLogMiddleware(MiddlewareMixin):
    """
    审计日志中间件

    将当前请求存储在线程本地存储中，供信号处理器访问
    """

    def process_request(self, request):
        """存储当前请求"""
        _thread_locals.request = request
        return None

    def process_response(self, request, response):
        """清理请求"""
        if hasattr(_thread_locals, 'request'):
            delattr(_thread_locals, 'request')
        return response


class RequestCaptureMiddleware(MiddlewareMixin):
    """
    请求捕获中间件

    捕获请求的详细信息，包括：
    - 用户信息
    - IP地址
    - User-Agent
    - 请求方法和路径
    """

    def process_request(self, request):
        """捕获请求信息"""
        # 存储请求
        _thread_locals.request = request

        # 存储客户端IP
        request.audit_log_ip = self.get_client_ip(request)

        # 存储用户代理
        request.audit_log_user_agent = request.META.get('HTTP_USER_AGENT', '')

        return None

    def process_response(self, request, response):
        """清理请求信息"""
        if hasattr(_thread_locals, 'request'):
            delattr(_thread_locals, 'request')
        return response

    @staticmethod
    def get_client_ip(request):
        """
        获取客户端IP地址

        Args:
            request: HttpRequest 对象

        Returns:
            str: IP地址
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


def get_current_request():
    """
    获取当前请求对象

    Returns:
        HttpRequest: 当前请求，如果没有则返回 None
    """
    return getattr(_thread_locals, 'request', None)


def get_current_user():
    """
    获取当前用户

    Returns:
        User: 当前用户，如果没有则返回 None
    """
    request = get_current_request()
    if request:
        return getattr(request, 'user', None)
    return None


def get_client_ip(request):
    """
    获取客户端IP地址

    Args:
        request: HttpRequest 对象

    Returns:
        str: IP地址
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
