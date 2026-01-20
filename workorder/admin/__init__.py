"""
Admin 模块

Django Admin 管理界面按业务领域拆分。

模块结构：
- mixins: 通用混入类
- base: 基础管理 (Customer, Department, Process)
- products: 产品管理 (Product, ProductGroup, ProductMaterial)
- materials: 物料采购管理 (Material, Supplier, PurchaseOrder)
- assets: 资产管理 (Artwork, Die, FoilingPlate, EmbossingPlate)
- core: 核心业务 (WorkOrder, WorkOrderProcess, WorkOrderTask)
- system: 系统管理 (UserProfile, Notification, TaskAssignmentRule)
- sales: 销售管理 (SalesOrder, SalesOrderItem)
- finance: 财务管理 (Invoice, Payment, Statement)
- inventory: 库存管理 (ProductStock, StockIn, StockOut, DeliveryOrder)
"""

# Django admin 补丁（必须在最前）
from .mixins import (
    FixedInlineModelAdminMixin,
    _patched_check_inlines,
)

# 应用 Django admin 检查器补丁
from django.contrib.admin.options import ModelAdmin
ModelAdmin.checks_class._check_inlines = _patched_check_inlines

# 导入各模块的 Admin 类
from .base import (
    CustomerAdmin,
    DepartmentAdmin,
    ProcessAdmin,
)

from .products import (
    ProductAdmin,
    ProductGroupAdmin,
    ProductGroupItemAdmin,
)

from .materials import (
    MaterialAdmin,
    SupplierAdmin,
    MaterialSupplierAdmin,
    PurchaseOrderAdmin,
    PurchaseOrderItemAdmin,
)

from .assets import (
    ArtworkAdmin,
    DieAdmin,
    FoilingPlateAdmin,
    EmbossingPlateAdmin,
)

from .core import (
    WorkOrderAdmin,
    WorkOrderProcessAdmin,
    WorkOrderMaterialAdmin,
    ProcessLogAdmin,
    WorkOrderTaskAdmin,
)

from .system import (
    UserProfileAdmin,
    WorkOrderApprovalLogAdmin,
    TaskAssignmentRuleAdmin,
    NotificationAdmin,
)

from .sales import (
    SalesOrderAdmin,
    SalesOrderItemAdmin,
)

from .finance import (
    CostCenterAdmin,
    CostItemAdmin,
    ProductionCostAdmin,
    InvoiceAdmin,
    PaymentAdmin,
    PaymentPlanAdmin,
    StatementAdmin,
)

from .inventory import (
    ProductStockAdmin,
    StockInAdmin,
    StockOutAdmin,
    DeliveryOrderAdmin,
    DeliveryItemAdmin,
    QualityInspectionAdmin,
)

__all__ = [
    # Mixins
    'FixedInlineModelAdminMixin',
    '_patched_check_inlines',

    # Base Admins
    'CustomerAdmin',
    'DepartmentAdmin',
    'ProcessAdmin',

    # Product Admins
    'ProductAdmin',
    'ProductGroupAdmin',
    'ProductGroupItemAdmin',

    # Material Admins
    'MaterialAdmin',
    'SupplierAdmin',
    'MaterialSupplierAdmin',
    'PurchaseOrderAdmin',
    'PurchaseOrderItemAdmin',

    # Asset Admins
    'ArtworkAdmin',
    'DieAdmin',
    'FoilingPlateAdmin',
    'EmbossingPlateAdmin',

    # Core Admins
    'WorkOrderAdmin',
    'WorkOrderProcessAdmin',
    'WorkOrderMaterialAdmin',
    'ProcessLogAdmin',
    'WorkOrderTaskAdmin',

    # System Admins
    'UserProfileAdmin',
    'WorkOrderApprovalLogAdmin',
    'TaskAssignmentRuleAdmin',
    'NotificationAdmin',

    # Sales Admins
    'SalesOrderAdmin',
    'SalesOrderItemAdmin',

    # Finance Admins
    'CostCenterAdmin',
    'CostItemAdmin',
    'ProductionCostAdmin',
    'InvoiceAdmin',
    'PaymentAdmin',
    'PaymentPlanAdmin',
    'StatementAdmin',

    # Inventory Admins
    'ProductStockAdmin',
    'StockInAdmin',
    'StockOutAdmin',
    'DeliveryOrderAdmin',
    'DeliveryItemAdmin',
    'QualityInspectionAdmin',
]
