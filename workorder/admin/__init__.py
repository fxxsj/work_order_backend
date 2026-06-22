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
- audit: 审计日志管理
"""

# 应用 Django admin 检查器补丁
from django.contrib import admin
from django.contrib.admin.options import ModelAdmin

# Django admin 补丁（必须在最前）
from .mixins import FixedInlineModelAdminMixin, _patched_check_inlines

ModelAdmin.checks_class._check_inlines = _patched_check_inlines

from .audit import (  # noqa: E402
    AuditLogAdmin,
    AuditLogExportAdmin,
    AuditLogSettingsAdmin,
)
from .assets import (  # noqa: E402
    ArtworkAdmin,
    DieAdmin,
    EmbossingPlateAdmin,
    FoilingPlateAdmin,
)

# 导入各模块的 Admin 类
from .base import (  # noqa: E402
    CustomerAdmin,
    DepartmentAdmin,
    ProcessAdmin,
)
from .core import (  # noqa: E402
    ProcessLogAdmin,
    TaskLogAdmin,
    WorkOrderAdmin,
    WorkOrderMaterialAdmin,
    WorkOrderProcessAdmin,
    WorkOrderTaskAdmin,
)
from .finance import (  # noqa: E402
    CostCenterAdmin,
    CostItemAdmin,
    InvoiceAdmin,
    PaymentAdmin,
    PaymentPlanAdmin,
    ProductionCostAdmin,
    StatementAdmin,
)
from .inventory import (  # noqa: E402
    DeliveryItemAdmin,
    DeliveryOrderAdmin,
    ProductStockAdmin,
    QualityInspectionAdmin,
    StockInAdmin,
    StockOutAdmin,
)
from .materials import (  # noqa: E402
    MaterialAdmin,
    MaterialStockLogAdmin,
    MaterialSupplierAdmin,
    PurchaseOrderAdmin,
    PurchaseOrderItemAdmin,
    PurchaseReceiveRecordAdmin,
    SupplierAdmin,
)
from .products import (  # noqa: E402
    ProductAdmin,
    ProductGroupAdmin,
    ProductGroupItemAdmin,
    ProductStockLogAdmin,
)
from .sales import (  # noqa: E402
    SalesOrderAdmin,
    SalesOrderItemAdmin,
)
from .site import configure_admin_site  # noqa: E402
from .system import (  # noqa: E402
    NotificationAdmin,
    NotificationTemplateAdmin,
    SystemNotificationSettingsAdmin,
    TaskAssignmentRuleAdmin,
    UserProfileAdmin,
    WorkOrderApprovalLogAdmin,
)

configure_admin_site(admin.site)

__all__ = [
    # Mixins
    "FixedInlineModelAdminMixin",
    "_patched_check_inlines",
    # Base Admins
    "CustomerAdmin",
    "DepartmentAdmin",
    "ProcessAdmin",
    # Product Admins
    "ProductAdmin",
    "ProductGroupAdmin",
    "ProductGroupItemAdmin",
    "ProductStockLogAdmin",
    # Material Admins
    "MaterialAdmin",
    "SupplierAdmin",
    "MaterialSupplierAdmin",
    "PurchaseOrderAdmin",
    "PurchaseOrderItemAdmin",
    "PurchaseReceiveRecordAdmin",
    "MaterialStockLogAdmin",
    # Asset Admins
    "ArtworkAdmin",
    "DieAdmin",
    "FoilingPlateAdmin",
    "EmbossingPlateAdmin",
    # Core Admins
    "WorkOrderAdmin",
    "WorkOrderProcessAdmin",
    "WorkOrderMaterialAdmin",
    "ProcessLogAdmin",
    "WorkOrderTaskAdmin",
    "TaskLogAdmin",
    # System Admins
    "UserProfileAdmin",
    "WorkOrderApprovalLogAdmin",
    "TaskAssignmentRuleAdmin",
    "NotificationAdmin",
    "NotificationTemplateAdmin",
    "SystemNotificationSettingsAdmin",
    # Sales Admins
    "SalesOrderAdmin",
    "SalesOrderItemAdmin",
    # Finance Admins
    "CostCenterAdmin",
    "CostItemAdmin",
    "ProductionCostAdmin",
    "InvoiceAdmin",
    "PaymentAdmin",
    "PaymentPlanAdmin",
    "StatementAdmin",
    # Inventory Admins
    "ProductStockAdmin",
    "StockInAdmin",
    "StockOutAdmin",
    "DeliveryOrderAdmin",
    "DeliveryItemAdmin",
    "QualityInspectionAdmin",
    # Audit Admins
    "AuditLogAdmin",
    "AuditLogExportAdmin",
    "AuditLogSettingsAdmin",
    "configure_admin_site",
]
