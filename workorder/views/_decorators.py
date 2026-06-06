"""View 层通用装饰器。"""

import logging
from functools import wraps

from rest_framework import status

from workorder.response import APIResponse
from workorder.services.service_errors import ServiceError

logger = logging.getLogger(__name__)


def handle_flow_errors(message_prefix: str = "操作失败："):
    """统一处理流程接口中的 ServiceError 和非预期异常。"""

    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            try:
                return func(self, request, *args, **kwargs)
            except ServiceError as exc:
                return APIResponse.error(message=str(exc), code=exc.code)
            except Exception as exc:
                logger.exception("流程接口异常: %s", func.__name__)
                return APIResponse.error(
                    message=f"{message_prefix}{str(exc)}",
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return wrapper

    return decorator
