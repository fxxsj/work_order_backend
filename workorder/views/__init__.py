"""
Views 模块

将所有视图集按业务领域拆分为独立模块，提高代码可维护性。
"""

# 导入所有视图集，保持向后兼容
from .base import (
    CustomerViewSet,
    DepartmentViewSet,
    ProcessViewSet,
)

from .products import (
    ProductViewSet,
    ProductMaterialViewSet,
    ProductGroupViewSet,
    ProductGroupItemViewSet,
)

from .materials import (
    MaterialViewSet,
    SupplierViewSet,
    MaterialSupplierViewSet,
)

from .assets import (
    ArtworkViewSet,
    DieViewSet,
    FoilingPlateViewSet,
    EmbossingPlateViewSet,
)

from .core import (
    WorkOrderViewSet,
    WorkOrderProcessViewSet,
    WorkOrderTaskViewSet,
    WorkOrderProductViewSet,
    WorkOrderMaterialViewSet,
    ProcessLogViewSet,
)

from .system import (
    NotificationViewSet,
    TaskAssignmentRuleViewSet,
)

from .sales import (
    SalesOrderViewSet,
    SalesOrderItemViewSet,
    PurchaseOrderViewSet,
    PurchaseOrderItemViewSet,
)

__all__ = [
    # 基础视图集
    'CustomerViewSet',
    'DepartmentViewSet',
    'ProcessViewSet',

    # 产品视图集
    'ProductViewSet',
    'ProductMaterialViewSet',
    'ProductGroupViewSet',
    'ProductGroupItemViewSet',

    # 物料视图集
    'MaterialViewSet',
    'SupplierViewSet',
    'MaterialSupplierViewSet',

    # 资产视图集
    'ArtworkViewSet',
    'DieViewSet',
    'FoilingPlateViewSet',
    'EmbossingPlateViewSet',

    # 核心业务视图集
    'WorkOrderViewSet',
    'WorkOrderProcessViewSet',
    'WorkOrderTaskViewSet',
    'WorkOrderProductViewSet',
    'WorkOrderMaterialViewSet',
    'ProcessLogViewSet',

    # 系统视图集
    'NotificationViewSet',
    'TaskAssignmentRuleViewSet',

    # 销售视图集
    'SalesOrderViewSet',
    'SalesOrderItemViewSet',
    'PurchaseOrderViewSet',
    'PurchaseOrderItemViewSet',
]
