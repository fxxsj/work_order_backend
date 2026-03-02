"""
多级审核权限策略
"""

from __future__ import annotations

from workorder.services.service_errors import ServiceError


def require_permission(user, perm: str, message: str = "权限不足", code: int = 403) -> None:
    if not user.has_perm(perm):
        raise ServiceError(message=message, code=code)
