"""
Models 模块入口

将所有模型按业务领域拆分为独立模块，提高代码可维护性。
Django 会导入 app 的 models 包来注册模型，因此这里显式导入各领域模型。

模块结构：
- base: 基础管理模型 (Customer, Department, Process, UserProfile)
- products: 产品管理模型 (Product, ProductGroup, ProductMaterial, etc.)
- materials: 物料管理模型 (Material, Supplier, MaterialSupplier, etc.)
- assets: 资产管理模型 (Artwork, Die, FoilingPlate, EmbossingPlate, etc.)
- core: 核心业务模型 (WorkOrder, WorkOrderProcess, WorkOrderTask, etc.)
- system: 系统管理模型 (WorkOrderApprovalLog, Notification, TaskAssignmentRule)
- sales: 销售管理模型 (SalesOrder, SalesOrderItem)
"""

from .assets import (
    Artwork,
    ArtworkImage,
    ArtworkProduct,
    Die,
    DieImage,
    DieProduct,
    EmbossingPlate,
    EmbossingPlateImage,
    EmbossingPlateProduct,
    FoilingPlate,
    FoilingPlateImage,
    FoilingPlateProduct,
)
from .audit import AuditLog, AuditLogExport, AuditLogSettings
from .base import Customer, Department, Process
from .core import (
    APPROVED_ORDER_EDITABLE_FIELDS,
    APPROVED_ORDER_PROTECTED_FIELDS,
    ProcessLog,
    TaskLog,
    WorkOrder,
    WorkOrderMaterial,
    WorkOrderProcess,
    WorkOrderProduct,
    WorkOrderTask,
)
from .finance import (
    CostCenter,
    CostItem,
    Invoice,
    Payment,
    PaymentPlan,
    ProductionCost,
    Statement,
)
from .finance import SupplierPayment  # noqa: F401
from .inventory import (
    DeliveryItem,
    DeliveryOrder,
    ProductStock,
    QualityInspection,
    StockIn,
    StockOut,
)
from .materials import (
    Material,
    MaterialStockLog,
    MaterialSupplier,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceiveRecord,
    Supplier,
)
from .products import (
    Product,
    ProductImage,
    ProductGroup,
    ProductGroupItem,
    ProductMaterial,
    ProductStockLog,
)
from .sales import SalesOrder, SalesOrderItem
from .system import (
    Notification,
    NotificationTemplate,
    SystemNotificationSettings,
    TaskAssignmentRule,
    UserProfile,
    WorkOrderApprovalLog,
)

__all__ = [
    # 基础模型
    "Customer",
    "Department",
    "Process",
    "APPROVED_ORDER_PROTECTED_FIELDS",
    "APPROVED_ORDER_EDITABLE_FIELDS",
    # 产品模型
    "Product",
    "ProductImage",
    "ProductGroup",
    "ProductGroupItem",
    "ProductMaterial",
    "ProductStockLog",
    # 物料模型
    "Material",
    "Supplier",
    "MaterialSupplier",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "PurchaseReceiveRecord",
    "MaterialStockLog",
    # 资产模型
    "Artwork",
    "ArtworkImage",
    "ArtworkProduct",
    "Die",
    "DieImage",
    "DieProduct",
    "FoilingPlate",
    "FoilingPlateImage",
    "FoilingPlateProduct",
    "EmbossingPlate",
    "EmbossingPlateImage",
    "EmbossingPlateProduct",
    # 核心业务模型
    "WorkOrder",
    "WorkOrderProcess",
    "WorkOrderProduct",
    "WorkOrderMaterial",
    "WorkOrderTask",
    "ProcessLog",
    "TaskLog",
    # 系统模型
    "UserProfile",
    "WorkOrderApprovalLog",
    "Notification",
    "NotificationTemplate",
    "SystemNotificationSettings",
    "TaskAssignmentRule",
    # 销售模型
    "SalesOrder",
    "SalesOrderItem",
    # 财务模型
    "CostCenter",
    "CostItem",
    "ProductionCost",
    "Invoice",
    "Payment",
    "PaymentPlan",
    "Statement",
    # 库存模型
    "ProductStock",
    "StockIn",
    "StockOut",
    "DeliveryOrder",
    "DeliveryItem",
    "QualityInspection",
    # 审计日志
    "AuditLog",
    "AuditLogExport",
    "AuditLogSettings",
]
