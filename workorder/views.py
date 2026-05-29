"""
Views 模块 - 保持向后兼容

该文件已被拆分为多个模块文件以提高可维护性。
所有视图集现在按功能组织在 views/ 目录下。

模块结构：
- views.base: 基础数据视图集（客户、部门、工序）
- views.products: 产品相关视图集
- views.materials: 物料相关视图集
- views.assets: 资产相关视图集（图稿、刀模、烫金版、压凸版）
- views.core: 核心业务视图集（施工单、工序、任务、日志）
- views.system: 系统管理视图集（通知、任务分派规则）
- views.sales: 客户订单视图集

为了保持向后兼容，本文件重新导出所有视图集。
"""

# 从模块中导入所有视图集
from .views import (
    # 基础视图集
    CustomerViewSet,
    DepartmentViewSet,
    ProcessViewSet,

    # 产品视图集
    ProductViewSet,
    ProductMaterialViewSet,
    ProductGroupViewSet,
    ProductGroupItemViewSet,

    # 物料视图集
    MaterialViewSet,
    SupplierViewSet,
    MaterialSupplierViewSet,

    # 资产视图集
    ArtworkViewSet,
    DieViewSet,
    FoilingPlateViewSet,
    EmbossingPlateViewSet,

    # 核心业务视图集
    WorkOrderViewSet,
    WorkOrderProcessViewSet,
    WorkOrderTaskViewSet,
    WorkOrderProductViewSet,
    WorkOrderMaterialViewSet,
    ProcessLogViewSet,

    # 系统视图集
    NotificationViewSet,
    TaskAssignmentRuleViewSet,

    # 销售视图集
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
