"""
工作订单管理系统 - 数据模型

本文件已拆分为多个模块文件以提高可维护性。
所有模型已移动到 models/ 目录下的子模块中。

为了保持向后兼容性，这里重新导出所有模型。
"""

# 从子模块导入所有模型
from .models import *

# 保持向后兼容：允许从 workorder.models 直接导入
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
