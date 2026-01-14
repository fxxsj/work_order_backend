"""
Serializers 模块

将所有序列化器按业务领域拆分为独立模块，提高代码可维护性。
"""

# 导入所有序列化器，保持向后兼容
from .base import (
    UserSerializer,
    CustomerSerializer,
    DepartmentSerializer,
    ProcessSerializer,
)

from .products import (
    ProductSerializer,
    ProductMaterialSerializer,
    ProductGroupSerializer,
    ProductGroupItemSerializer,
)

from .materials import (
    MaterialSerializer,
    SupplierSerializer,
    MaterialSupplierSerializer,
    PurchaseOrderListSerializer,
    PurchaseOrderDetailSerializer,
    PurchaseOrderItemSerializer,
)

from .assets import (
    ArtworkSerializer,
    ArtworkProductSerializer,
    DieSerializer,
    DieProductSerializer,
    FoilingPlateSerializer,
    FoilingPlateProductSerializer,
    EmbossingPlateSerializer,
    EmbossingPlateProductSerializer,
)

from .core import (
    WorkOrderListSerializer,
    WorkOrderDetailSerializer,
    WorkOrderCreateUpdateSerializer,
    WorkOrderProcessSerializer,
    WorkOrderProcessUpdateSerializer,
    WorkOrderTaskSerializer,
    WorkOrderMaterialSerializer,
    WorkOrderProductSerializer,
    ProcessLogSerializer,
    TaskLogSerializer,
)

from .system import (
    WorkOrderApprovalLogSerializer,
    NotificationSerializer,
    TaskAssignmentRuleSerializer,
)

from .sales import (
    SalesOrderListSerializer,
    SalesOrderDetailSerializer,
    SalesOrderItemSerializer,
)

__all__ = [
    # 基础序列化器
    'UserSerializer',
    'CustomerSerializer',
    'DepartmentSerializer',
    'ProcessSerializer',

    # 产品序列化器
    'ProductSerializer',
    'ProductMaterialSerializer',
    'ProductGroupSerializer',
    'ProductGroupItemSerializer',

    # 物料序列化器
    'MaterialSerializer',
    'SupplierSerializer',
    'MaterialSupplierSerializer',
    'PurchaseOrderListSerializer',
    'PurchaseOrderDetailSerializer',
    'PurchaseOrderItemSerializer',

    # 资产序列化器
    'ArtworkSerializer',
    'ArtworkProductSerializer',
    'DieSerializer',
    'DieProductSerializer',
    'FoilingPlateSerializer',
    'FoilingPlateProductSerializer',
    'EmbossingPlateSerializer',
    'EmbossingPlateProductSerializer',

    # 核心业务序列化器
    'WorkOrderListSerializer',
    'WorkOrderDetailSerializer',
    'WorkOrderCreateUpdateSerializer',
    'WorkOrderProcessSerializer',
    'WorkOrderProcessUpdateSerializer',
    'WorkOrderTaskSerializer',
    'WorkOrderMaterialSerializer',
    'WorkOrderProductSerializer',
    'ProcessLogSerializer',
    'TaskLogSerializer',

    # 系统序列化器
    'WorkOrderApprovalLogSerializer',
    'NotificationSerializer',
    'TaskAssignmentRuleSerializer',

    # 销售序列化器
    'SalesOrderListSerializer',
    'SalesOrderDetailSerializer',
    'SalesOrderItemSerializer',
]
