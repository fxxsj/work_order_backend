from functools import wraps
from workorder.response import APIResponse
from workorder.services.approval_service import ApprovalService
from workorder.services.service_errors import ServiceError


def require_approval_permission(model_class):
    """审核权限装饰器"""

    def decorator(action_func):
        @wraps(action_func)
        def wrapper(self, request, *args, **kwargs):
            obj = self.get_object()
            service = ApprovalService(model_class)
            try:
                service.validate_approval_permission(request.user, obj)
            except ServiceError as e:
                return APIResponse.error(message=str(e), code=e.code)
            return action_func(self, request, *args, **kwargs)

        return wrapper

    return decorator


def require_submit_permission(model_class):
    """提交审核权限装饰器"""

    def decorator(action_func):
        @wraps(action_func)
        def wrapper(self, request, *args, **kwargs):
            obj = self.get_object()
            service = ApprovalService(model_class)
            try:
                service.validate_submit_permission(request.user, obj)
            except ServiceError as e:
                return APIResponse.error(message=str(e), code=e.code)
            return action_func(self, request, *args, **kwargs)

        return wrapper

    return decorator
