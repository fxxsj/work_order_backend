"""
用户角色判断工具函数。

统一入口，避免在业务代码中散落 user.groups.filter(name=...).exists() 查询。
"""

from django.contrib.auth.models import User

from workorder.constants.role_codes import (
    ADMIN,
    FINANCE,
    INVENTORY,
    MANAGER,
    OPERATOR,
    QUALITY,
    SALES,
    SUPERVISOR,
)


def get_user_role_codes(user) -> list[str]:
    """
    获取用户所有角色代码。

    Args:
        user: User 实例或用户对象

    Returns:
        list[str]: 用户所属的角色代码列表，如 ['sales', 'supervisor']
    """
    if not user or not user.is_authenticated:
        return []

    if isinstance(user, int):
        try:
            user = User.objects.get(pk=user)
        except User.DoesNotExist:
            return []

    return list(user.groups.values_list("name", flat=True))


def is_sales_user(user) -> bool:
    """判断用户是否为业务员。"""
    if not user or not user.is_authenticated:
        return False
    if isinstance(user, int):
        try:
            user = User.objects.get(pk=user)
        except User.DoesNotExist:
            return False
    return user.groups.filter(name=SALES).exists()


def is_supervisor_user(user) -> bool:
    """判断用户是否为主管。"""
    if not user or not user.is_authenticated:
        return False
    if isinstance(user, int):
        try:
            user = User.objects.get(pk=user)
        except User.DoesNotExist:
            return False
    return user.groups.filter(name=SUPERVISOR).exists()


def is_operator_user(user) -> bool:
    """判断用户是否为操作员。"""
    if not user or not user.is_authenticated:
        return False
    if isinstance(user, int):
        try:
            user = User.objects.get(pk=user)
        except User.DoesNotExist:
            return False
    return user.groups.filter(name=OPERATOR).exists()


def is_manager_user(user) -> bool:
    """判断用户是否为经理。"""
    if not user or not user.is_authenticated:
        return False
    if isinstance(user, int):
        try:
            user = User.objects.get(pk=user)
        except User.DoesNotExist:
            return False
    return user.groups.filter(name=MANAGER).exists()


def is_finance_user(user) -> bool:
    """判断用户是否为财务。"""
    if not user or not user.is_authenticated:
        return False
    if isinstance(user, int):
        try:
            user = User.objects.get(pk=user)
        except User.DoesNotExist:
            return False
    return user.groups.filter(name=FINANCE).exists()


def is_inventory_user(user) -> bool:
    """判断用户是否为仓储。"""
    if not user or not user.is_authenticated:
        return False
    if isinstance(user, int):
        try:
            user = User.objects.get(pk=user)
        except User.DoesNotExist:
            return False
    return user.groups.filter(name=INVENTORY).exists()


def is_quality_user(user) -> bool:
    """判断用户是否为质检。"""
    if not user or not user.is_authenticated:
        return False
    if isinstance(user, int):
        try:
            user = User.objects.get(pk=user)
        except User.DoesNotExist:
            return False
    return user.groups.filter(name=QUALITY).exists()


def is_admin_user(user) -> bool:
    """判断用户是否为系统管理员。"""
    if not user or not user.is_authenticated:
        return False
    if isinstance(user, int):
        try:
            user = User.objects.get(pk=user)
        except User.DoesNotExist:
            return False
    return user.groups.filter(name=ADMIN).exists()
