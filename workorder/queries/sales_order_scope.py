"""客户订单查询作用域工具。

该模块提供 SalesOrder 查询集的权限/数据范围过滤，供 views 与 services 共用，
避免 service 层反向依赖 views 层的私有函数。
"""

from workorder.permission_utils import PermissionUtils


def scope_sales_orders(queryset, user):
    """根据当前用户权限过滤客户订单查询集。

    Args:
        queryset: SalesOrder QuerySet
        user: 当前请求用户

    Returns:
        QuerySet: 过滤后的查询集
    """
    if not user.is_authenticated:
        return queryset.none()
    if user.is_superuser or PermissionUtils.is_finance_user(user):
        return queryset

    scope = PermissionUtils.build_sales_order_scope_q(user, "")
    return queryset.filter(scope).distinct()


__all__ = ["scope_sales_orders"]
