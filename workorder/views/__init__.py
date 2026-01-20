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
    ArtworkProductViewSet,
    DieProductViewSet,
    FoilingPlateProductViewSet,
    EmbossingPlateProductViewSet,
)

# 核心业务视图集（已拆分）
from .work_orders import WorkOrderViewSet
from .work_order_processes import WorkOrderProcessViewSet
from .work_order_tasks import WorkOrderTaskViewSet
from .work_order_products import WorkOrderProductViewSet
from .work_order_materials import WorkOrderMaterialViewSet
from .process_logs import ProcessLogViewSet

from .system import (
    TaskAssignmentRuleViewSet,
)

from .sales import (
    SalesOrderViewSet,
    SalesOrderItemViewSet,
    PurchaseOrderViewSet,
    PurchaseOrderItemViewSet,
)

from .finance import (
    CostCenterViewSet,
    CostItemViewSet,
    ProductionCostViewSet,
    InvoiceViewSet,
    PaymentViewSet,
    PaymentPlanViewSet,
    StatementViewSet,
)

from .inventory import (
    ProductStockViewSet,
    StockInViewSet,
    StockOutViewSet,
    DeliveryOrderViewSet,
    DeliveryItemViewSet,
    QualityInspectionViewSet,
)

from .multi_level_approval import (
    ApprovalWorkflowViewSet,
    ApprovalStepViewSet,
    MultiLevelApprovalViewSet,
    UrgentOrderViewSet,
    ApprovalReportViewSet,
)

from .notification import (
    NotificationViewSet,
    SystemNotificationViewSet,
    UserNotificationSettingsViewSet,
    NotificationTemplateViewSet,
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
    'ArtworkProductViewSet',
    'DieProductViewSet',
    'FoilingPlateProductViewSet',
    'EmbossingPlateProductViewSet',

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

    # 财务视图集
    'CostCenterViewSet',
    'CostItemViewSet',
    'ProductionCostViewSet',
    'InvoiceViewSet',
    'PaymentViewSet',
    'PaymentPlanViewSet',
    'StatementViewSet',

    # 库存视图集
    'ProductStockViewSet',
    'StockInViewSet',
    'StockOutViewSet',
    'DeliveryOrderViewSet',
    'DeliveryItemViewSet',
    'QualityInspectionViewSet',

    # 审批视图集
    'ApprovalWorkflowViewSet',
    'ApprovalStepViewSet',
    'MultiLevelApprovalViewSet',
    'UrgentOrderViewSet',
    'ApprovalReportViewSet',

    # 通知视图集
    'NotificationViewSet',
    'SystemNotificationViewSet',
    'UserNotificationSettingsViewSet',
    'NotificationTemplateViewSet',
]
