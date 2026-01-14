"""
Models 模块

将所有模型按业务领域拆分为独立模块，提高代码可维护性。
"""

from .base import (
    Customer,
    Department,
    Process
)

from .products import (
    Product,
    ProductGroup,
    ProductGroupItem,
    ProductMaterial,
    ProductStockLog
)

from .materials import (
    Material,
    Supplier,
    MaterialSupplier,
    PurchaseOrder,
    PurchaseOrderItem
)

from .assets import (
    Artwork,
    ArtworkProduct,
    Die,
    DieProduct,
    FoilingPlate,
    FoilingPlateProduct,
    EmbossingPlate,
    EmbossingPlateProduct
)

from .core import (
    WorkOrder,
    WorkOrderProcess,
    WorkOrderProduct,
    WorkOrderMaterial,
    WorkOrderTask,
    ProcessLog,
    TaskLog
)

from .system import (
    UserProfile,
    WorkOrderApprovalLog,
    Notification,
    TaskAssignmentRule
)

from .sales import (
    SalesOrder,
    SalesOrderItem
)

__all__ = [
    # 基础模型
    'Customer',
    'Department',
    'Process',

    # 产品模型
    'Product',
    'ProductGroup',
    'ProductGroupItem',
    'ProductMaterial',
    'ProductStockLog',

    # 物料模型
    'Material',
    'Supplier',
    'MaterialSupplier',
    'PurchaseOrder',
    'PurchaseOrderItem',

    # 资产模型
    'Artwork',
    'ArtworkProduct',
    'Die',
    'DieProduct',
    'FoilingPlate',
    'FoilingPlateProduct',
    'EmbossingPlate',
    'EmbossingPlateProduct',

    # 核心业务模型
    'WorkOrder',
    'WorkOrderProcess',
    'WorkOrderProduct',
    'WorkOrderMaterial',
    'WorkOrderTask',
    'ProcessLog',
    'TaskLog',

    # 系统模型
    'UserProfile',
    'WorkOrderApprovalLog',
    'Notification',
    'TaskAssignmentRule',

    # 销售模型
    'SalesOrder',
    'SalesOrderItem',
]
