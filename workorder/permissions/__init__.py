"""自定义权限类"""

from .permission_classes import (
    CustomerDataPermission,
    IsOwnerOrReadOnly,
    IsStaffOrReadOnly,
    SuperuserFriendlyModelPermissions,
    WorkOrderAssetPermission,
    WorkOrderDataPermission,
    WorkOrderMaterialPermission,
    WorkOrderProcessPermission,
    WorkOrderProductPermission,
    WorkOrderSupportingDataPermission,
    WorkOrderTaskPermission,
)

__all__ = [
    "SuperuserFriendlyModelPermissions",
    "CustomerDataPermission",
    "WorkOrderSupportingDataPermission",
    "IsStaffOrReadOnly",
    "IsOwnerOrReadOnly",
    "WorkOrderAssetPermission",
    "WorkOrderProcessPermission",
    "WorkOrderMaterialPermission",
    "WorkOrderProductPermission",
    "WorkOrderTaskPermission",
    "WorkOrderDataPermission",
]
