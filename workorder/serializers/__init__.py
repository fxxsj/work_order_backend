"""
Serializers 模块

将所有序列化器按业务领域拆分为独立模块，提高代码可维护性。
"""

from .assets import (
    ArtworkProductSerializer,
    ArtworkSerializer,
    DieProductSerializer,
    DieSerializer,
    EmbossingPlateProductSerializer,
    EmbossingPlateSerializer,
    FoilingPlateProductSerializer,
    FoilingPlateSerializer,
)

# 导入所有序列化器，保持向后兼容
from .base import (
    CustomerSerializer,
    DepartmentSerializer,
    ProcessSerializer,
    UserSerializer,
)
from .core import (
    ProcessLogSerializer,
    TaskLogSerializer,
    WorkOrderCreateUpdateSerializer,
    WorkOrderDetailSerializer,
    WorkOrderListSerializer,
    WorkOrderMaterialSerializer,
    WorkOrderProcessSerializer,
    WorkOrderProcessUpdateSerializer,
    WorkOrderProductSerializer,
    WorkOrderTaskSerializer,
)
from .finance import (
    CostCenterSerializer,
    CostItemSerializer,
    InvoiceCreateSerializer,
    InvoiceSerializer,
    InvoiceUpdateSerializer,
    PaymentCreateSerializer,
    PaymentPlanSerializer,
    PaymentSerializer,
    PaymentUpdateSerializer,
    ProductionCostSerializer,
    ProductionCostUpdateSerializer,
    StatementCreateSerializer,
    StatementSerializer,
)
from .inventory import (
    DeliveryItemSerializer,
    DeliveryOrderCreateSerializer,
    DeliveryOrderListSerializer,
    DeliveryOrderSerializer,
    DeliveryOrderUpdateSerializer,
    ProductStockSerializer,
    ProductStockUpdateSerializer,
    QualityInspectionCreateSerializer,
    QualityInspectionSerializer,
    QualityInspectionUpdateSerializer,
    StockInCreateSerializer,
    StockInSerializer,
    StockOutSerializer,
)
from .materials import (
    MaterialSerializer,
    MaterialSupplierSerializer,
    PurchaseOrderDetailSerializer,
    PurchaseOrderItemSerializer,
    PurchaseOrderListSerializer,
    SupplierSerializer,
)
from .products import (
    ProductGroupItemSerializer,
    ProductGroupSerializer,
    ProductMaterialSerializer,
    ProductSerializer,
)
from .sales import (
    SalesOrderDetailSerializer,
    SalesOrderItemSerializer,
    SalesOrderListSerializer,
)
from .system import (
    NotificationSerializer,
    TaskAssignmentRuleSerializer,
    WorkOrderApprovalLogSerializer,
)

__all__ = [
    # 基础序列化器
    "UserSerializer",
    "CustomerSerializer",
    "DepartmentSerializer",
    "ProcessSerializer",
    # 产品序列化器
    "ProductSerializer",
    "ProductMaterialSerializer",
    "ProductGroupSerializer",
    "ProductGroupItemSerializer",
    # 物料序列化器
    "MaterialSerializer",
    "SupplierSerializer",
    "MaterialSupplierSerializer",
    "PurchaseOrderListSerializer",
    "PurchaseOrderDetailSerializer",
    "PurchaseOrderItemSerializer",
    # 资产序列化器
    "ArtworkSerializer",
    "ArtworkProductSerializer",
    "DieSerializer",
    "DieProductSerializer",
    "FoilingPlateSerializer",
    "FoilingPlateProductSerializer",
    "EmbossingPlateSerializer",
    "EmbossingPlateProductSerializer",
    # 核心业务序列化器
    "WorkOrderListSerializer",
    "WorkOrderDetailSerializer",
    "WorkOrderCreateUpdateSerializer",
    "WorkOrderProcessSerializer",
    "WorkOrderProcessUpdateSerializer",
    "WorkOrderTaskSerializer",
    "WorkOrderMaterialSerializer",
    "WorkOrderProductSerializer",
    "ProcessLogSerializer",
    "TaskLogSerializer",
    # 系统序列化器
    "WorkOrderApprovalLogSerializer",
    "NotificationSerializer",
    "TaskAssignmentRuleSerializer",
    # 销售序列化器
    "SalesOrderListSerializer",
    "SalesOrderDetailSerializer",
    "SalesOrderItemSerializer",
    # 财务序列化器
    "CostCenterSerializer",
    "CostItemSerializer",
    "ProductionCostSerializer",
    "ProductionCostUpdateSerializer",
    "InvoiceSerializer",
    "InvoiceCreateSerializer",
    "InvoiceUpdateSerializer",
    "PaymentSerializer",
    "PaymentCreateSerializer",
    "PaymentUpdateSerializer",
    "PaymentPlanSerializer",
    "StatementSerializer",
    "StatementCreateSerializer",
    # 库存序列化器
    "ProductStockSerializer",
    "ProductStockUpdateSerializer",
    "StockInSerializer",
    "StockInCreateSerializer",
    "StockOutSerializer",
    "DeliveryItemSerializer",
    "DeliveryOrderSerializer",
    "DeliveryOrderListSerializer",
    "DeliveryOrderCreateSerializer",
    "DeliveryOrderUpdateSerializer",
    "QualityInspectionSerializer",
    "QualityInspectionCreateSerializer",
    "QualityInspectionUpdateSerializer",
]
