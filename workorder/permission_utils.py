"""
权限工具类

提供缓存和优化的权限检查方法，减少数据库查询
"""
from django.core.cache import cache
from django.contrib.auth.models import Permission
from django.db.models import Q


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

    FINANCE_PERMISSION_CODES = (
        "workorder.view_invoice",
        "workorder.change_invoice",
        "workorder.view_payment",
        "workorder.change_payment",
        "workorder.view_paymentplan",
        "workorder.change_paymentplan",
        "workorder.view_statement",
        "workorder.change_statement",
        "workorder.view_productioncost",
        "workorder.change_productioncost",
    )

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

    @staticmethod
    def is_finance_user(user):
        """判断用户是否属于财务视角账号。"""
        return PermissionUtils.has_any_permission(
            user, PermissionUtils.FINANCE_PERMISSION_CODES
        )

    @staticmethod
    def build_customer_scope_q(user, customer_path="customer"):
        """按客户业务员构建数据范围。"""
        prefix = PermissionUtils._prefix(customer_path)
        return Q(**{f"{prefix}salesperson": user})

    @staticmethod
    def build_sales_order_scope_q(user, sales_order_path="sales_order"):
        """按客户订单归属构建数据范围。"""
        prefix = PermissionUtils._prefix(sales_order_path)
        scope = Q(**{f"{prefix}created_by": user}) | Q(
            **{f"{prefix}customer__salesperson": user}
        )
        department_ids = PermissionCache.get_user_departments(user)
        if department_ids:
            scope |= Q(
                **{
                    f"{prefix}source_work_orders__order_processes__department_id__in": department_ids
                }
            )
        return scope

    @staticmethod
    def build_work_order_scope_q(user, work_order_path="work_order"):
        """按施工单归属构建数据范围。"""
        prefix = PermissionUtils._prefix(work_order_path)
        scope = Q(**{f"{prefix}created_by": user}) | Q(
            **{f"{prefix}customer__salesperson": user}
        )
        department_ids = PermissionCache.get_user_departments(user)
        if department_ids:
            scope |= Q(
                **{f"{prefix}order_processes__department_id__in": department_ids}
            )
        return scope

    @staticmethod
    def build_department_scope_q(user, relation_paths):
        """按部门关系构建数据范围。"""
        department_ids = PermissionCache.get_user_departments(user)
        scope = Q()
        if not department_ids:
            return scope
        for relation_path in relation_paths:
            prefix = PermissionUtils._prefix(relation_path)
            scope |= Q(**{f"{prefix}id__in": department_ids})
        return scope

    @staticmethod
    def _prefix(path):
        return f"{path}__" if path else ""


def apply_data_scope(
    queryset,
    user,
    *,
    customer_path=None,
    sales_order_path=None,
    work_order_path=None,
    ownership_paths=(),
    bypass_check=None,
):
    """Apply user-based data scope filtering to a queryset.

    Unified replacement for _scope_finance_queryset and _apply_user_scope.

    Args:
        queryset: The base queryset to filter.
        user: The current request user.
        customer_path: FK path to Customer model for salesperson scoping.
        sales_order_path: FK path to SalesOrder for order scoping.
        work_order_path: FK path to WorkOrder for work order scoping.
        ownership_paths: Tuple of FK paths for direct ownership checks.
        bypass_check: Optional callable(user) -> bool. If returns True,
            the queryset is returned unfiltered (e.g. for finance users).
    """
    if not user.is_authenticated:
        return queryset.none()
    if user.is_superuser:
        return queryset
    if bypass_check and bypass_check(user):
        return queryset

    scope = Q()
    if customer_path:
        scope |= PermissionUtils.build_customer_scope_q(user, customer_path)
    if sales_order_path:
        scope |= PermissionUtils.build_sales_order_scope_q(user, sales_order_path)
    if work_order_path:
        scope |= PermissionUtils.build_work_order_scope_q(user, work_order_path)
    for ownership_path in ownership_paths:
        scope |= Q(**{ownership_path: user})

    if not scope.children:
        return queryset.none()
    return queryset.filter(scope).distinct()


def apply_department_scope(queryset, department_id, path):
    """Filter queryset to a specific department along the given relation path."""
    if not department_id:
        return queryset
    filter_key = f"{path}__id"
    return queryset.filter(**{filter_key: department_id}).distinct()
