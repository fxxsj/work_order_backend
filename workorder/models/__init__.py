"""
Models 模块

将所有模型按业务领域拆分为独立模块，提高代码可维护性。

模块结构：
- base: 基础管理模型 (Customer, Department, Process, UserProfile)
- products: 产品管理模型 (Product, ProductGroup, ProductMaterial, etc.)
- materials: 物料管理模型 (Material, Supplier, MaterialSupplier, etc.)
- assets: 资产管理模型 (Artwork, Die, FoilingPlate, EmbossingPlate, etc.)
- core: 核心业务模型 (WorkOrder, WorkOrderProcess, WorkOrderTask, etc.)
- system: 系统管理模型 (WorkOrderApprovalLog, Notification, TaskAssignmentRule)
- sales: 销售管理模型 (SalesOrder, SalesOrderItem)
"""

# 导入所有模型，保持向后兼容
from .base import (
    Customer,
    Department,
    Process,
)

from .products import (
    Product,
    ProductGroup,
    ProductGroupItem,
    ProductMaterial,
    ProductStockLog,
)

from .materials import (
    Material,
    Supplier,
    MaterialSupplier,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceiveRecord,
)

from .assets import (
    Artwork,
    ArtworkProduct,
    Die,
    DieProduct,
    FoilingPlate,
    FoilingPlateProduct,
    EmbossingPlate,
    EmbossingPlateProduct,
)

from .core import (
    APPROVED_ORDER_PROTECTED_FIELDS,
    APPROVED_ORDER_EDITABLE_FIELDS,
    WorkOrder,
    WorkOrderProcess,
    WorkOrderProduct,
    WorkOrderMaterial,
    WorkOrderTask,
    ProcessLog,
    TaskLog,
)

from .system import (
    UserProfile,
    WorkOrderApprovalLog,
    Notification,
    TaskAssignmentRule,
)

from .sales import (
    SalesOrder,
    SalesOrderItem,
)

from .finance import (
    CostCenter,
    CostItem,
    ProductionCost,
    Invoice,
    Payment,
    PaymentPlan,
    Statement,
)

from .inventory import (
    ProductStock,
    StockIn,
    StockOut,
    DeliveryOrder,
    DeliveryItem,
    QualityInspection,
)

from .multi_level_approval import (
    ApprovalWorkflow,
    ApprovalStep,
    ApprovalRule,
    ApprovalEscalation,
    MultiLevelApprovalService,
    UrgentOrderService,
)

__all__ = [
    # 基础模型
    'Customer',
    'Department',
    'Process',
    'APPROVED_ORDER_PROTECTED_FIELDS',
    'APPROVED_ORDER_EDITABLE_FIELDS',

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
    'PurchaseReceiveRecord',

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

    # 多级审核模型
    'ApprovalWorkflow',
    'ApprovalStep',
    'ApprovalRule',
    'ApprovalEscalation',
    'MultiLevelApprovalService',
    'UrgentOrderService',

    # 财务模型
    'CostCenter',
    'CostItem',
    'ProductionCost',
    'Invoice',
    'Payment',
    'PaymentPlan',
    'Statement',

    # 库存模型
    'ProductStock',
    'StockIn',
    'StockOut',
    'DeliveryOrder',
    'DeliveryItem',
    'QualityInspection',
]
