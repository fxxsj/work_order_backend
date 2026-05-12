"""
权限相关常量定义

此模块定义了系统权限相关的常量。
"""

from django.utils.translation import gettext_lazy as _

# 重新导出 role_codes 以保持兼容性
from .role_codes import (
    ROLE_CODES,
    ALL_ROLE_CODES,
    CODE_TO_LABEL,
    SALES,
    SUPERVISOR,
    MANAGER,
    OPERATOR,
    FINANCE,
    INVENTORY,
    QUALITY,
    ADMIN,
    resolve_role_code,
)

# 为了兼容性保留中文别名（已废弃，不应在新代码中使用）
from .role_codes import LABEL_TO_CODE

# ============================================================================
# 以下常量已废弃，请使用 role_codes.py 中的常量
# ============================================================================

# 兼容性别名（废弃）
UserRole = None  # 已废弃，请使用 role_codes 中的常量

class _DeprecatedUserRole:
    """废弃类，请使用 role_codes.ROLE_CODES"""
    ADMIN = 'admin'
    MANAGER = 'manager'
    SUPERVISOR = 'supervisor'
    OPERATOR = 'operator'
    SALESPERSON = 'sales'
    FINANCE = 'finance'
    WAREHOUSE = 'inventory'
    QUALITY = 'quality'

    @classmethod
    def to_code(cls, label):
        """将中文标签转为 code（兼容旧代码）"""
        return LABEL_TO_CODE.get(label)


# PermissionGroups 已废弃
PermissionGroups = None

# ============================================================================
# 权限操作常量（正常使用）
# ============================================================================

class PermissionAction:
    """权限操作常量"""

    VIEW = 'view'
    ADD = 'add'
    CHANGE = 'change'
    DELETE = 'delete'
    EXPORT = 'export'
    APPROVE = 'approve'
    ASSIGN = 'assign'

    CHOICES = [
        (VIEW, _('查看')),
        (ADD, _('添加')),
        (CHANGE, _('修改')),
        (DELETE, _('删除')),
        (EXPORT, _('导出')),
        (APPROVE, _('审核')),
        (ASSIGN, _('分派')),
    ]


# 资源权限前缀常量
WORKORDER = 'workorder'
TASK = 'task'
PROCESS = 'process'
CUSTOMER = 'customer'
PRODUCT = 'product'
MATERIAL = 'material'
SUPPLIER = 'supplier'