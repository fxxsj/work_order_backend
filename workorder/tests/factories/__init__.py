"""Test data factories for workorder app"""
from .base import DepartmentFactory, ProcessFactory
from .users import UserFactory
from .workorder import (
    CustomerFactory, ProductFactory, WorkOrderFactory, WorkOrderProcessFactory,
    WorkOrderTaskFactory, WorkOrderProductFactory
)
from .materials import (
    SupplierFactory, MaterialFactory, MaterialSupplierFactory,
    WorkOrderMaterialFactory, PurchaseOrderFactory, PurchaseOrderItemFactory,
    PurchaseReceiveRecordFactory
)

__all__ = [
    'DepartmentFactory', 'ProcessFactory', 'UserFactory',
    'CustomerFactory', 'ProductFactory', 'WorkOrderFactory', 'WorkOrderProcessFactory',
    'WorkOrderTaskFactory', 'WorkOrderProductFactory',
    'SupplierFactory', 'MaterialFactory', 'MaterialSupplierFactory',
    'WorkOrderMaterialFactory', 'PurchaseOrderFactory', 'PurchaseOrderItemFactory',
    'PurchaseReceiveRecordFactory',
]
