"""
权限工具类

提供缓存和优化的权限检查方法，减少数据库查询
"""
from django.core.cache import cache
from django.contrib.auth.models import Permission


class PermissionCache:
    """权限缓存工具类"""

    @staticmethod
    def get_user_departments(user, timeout=1800):
        """获取用户部门列表（带缓存）

        Args:
            user: 用户对象
            timeout: 缓存超时时间（秒），默认 30 分钟

        Returns:
            list: 部门 ID 列表
        """
        if not user.is_authenticated:
            return []

        cache_key = f'user_departments_{user.id}'
        departments = cache.get(cache_key)

        if departments is None:
            # 缓存未命中，从数据库获取
            if hasattr(user, 'profile') and user.profile:
                departments = list(user.profile.departments.values_list('id', flat=True))
            else:
                departments = []

            # 缓存 30 分钟
            cache.set(cache_key, departments, timeout)

        return departments

    @staticmethod
    def is_user_in_department(user, department_id, timeout=1800):
        """检查用户是否属于指定部门（带缓存）

        Args:
            user: 用户对象
            department_id: 部门 ID
            timeout: 缓存超时时间（秒）

        Returns:
            bool: 是否属于该部门
        """
        departments = PermissionCache.get_user_departments(user, timeout)
        return department_id in departments

    @staticmethod
    def clear_user_cache(user):
        """清除用户权限相关缓存

        Args:
            user: 用户对象
        """
        cache_key = f'user_departments_{user.id}'
        cache.delete(cache_key)

    @staticmethod
    def clear_all_user_cache():
        """清除所有用户权限缓存（谨慎使用）"""
        # 在用户部门变更时调用
        # 例如：用户被添加到新部门或从部门移除
        cache.delete_many([key for key in cache.keys('user_departments_*')])


class PermissionUtils:
    """权限工具类"""

    @staticmethod
    def has_permission(user, permission_codename):
        """检查用户是否有指定权限（支持缓存）

        Args:
            user: 用户对象
            permission_codename: 权限代码，如 'workorder.add_workorder'

        Returns:
            bool: 是否有权限
        """
        if not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        # 检查用户是否有该权限
        return user.has_perm(permission_codename)

    @staticmethod
    def has_any_permission(user, permission_codenames):
        """检查用户是否有任一指定权限

        Args:
            user: 用户对象
            permission_codenames: 权限代码列表

        Returns:
            bool: 是否有任一权限
        """
        if not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        return any(user.has_perm(perm) for perm in permission_codenames)

    @staticmethod
    def has_all_permissions(user, permission_codenames):
        """检查用户是否拥有所有指定权限

        Args:
            user: 用户对象
            permission_codenames: 权限代码列表

        Returns:
            bool: 是否拥有所有权限
        """
        if not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        return all(user.has_perm(perm) for perm in permission_codenames)
