from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomerViewSet, DepartmentViewSet, ProcessViewSet, ProductViewSet,
    ProductMaterialViewSet, MaterialViewSet,
    WorkOrderViewSet, WorkOrderProcessViewSet,
    WorkOrderProductViewSet, WorkOrderMaterialViewSet, ProcessLogViewSet,
    ArtworkViewSet, ArtworkProductViewSet,
    DieViewSet, DieProductViewSet, FoilingPlateViewSet, FoilingPlateProductViewSet,
    EmbossingPlateViewSet, EmbossingPlateProductViewSet,
    WorkOrderTaskViewSet, ProductGroupViewSet, ProductGroupItemViewSet,
    TaskAssignmentRuleViewSet, NotificationViewSet,
    SupplierViewSet, MaterialSupplierViewSet, PurchaseOrderViewSet, PurchaseOrderItemViewSet
)
from .auth_views import login_view, logout_view, get_current_user, register_view, get_salespersons, get_users_by_department

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'processes', ProcessViewSet)
router.register(r'products', ProductViewSet)
router.register(r'product-materials', ProductMaterialViewSet)
router.register(r'materials', MaterialViewSet)
router.register(r'suppliers', SupplierViewSet)
router.register(r'material-suppliers', MaterialSupplierViewSet)
router.register(r'purchase-orders', PurchaseOrderViewSet)
router.register(r'purchase-order-items', PurchaseOrderItemViewSet)
router.register(r'workorders', WorkOrderViewSet)
router.register(r'workorder-processes', WorkOrderProcessViewSet)
router.register(r'workorder-products', WorkOrderProductViewSet)
router.register(r'workorder-materials', WorkOrderMaterialViewSet)
router.register(r'workorder-tasks', WorkOrderTaskViewSet)
router.register(r'product-groups', ProductGroupViewSet)
router.register(r'product-group-items', ProductGroupItemViewSet)
router.register(r'process-logs', ProcessLogViewSet)
router.register(r'task-assignment-rules', TaskAssignmentRuleViewSet)
router.register(r'notifications', NotificationViewSet)
router.register(r'artworks', ArtworkViewSet)
router.register(r'artwork-products', ArtworkProductViewSet)
router.register(r'dies', DieViewSet)
router.register(r'die-products', DieProductViewSet)
router.register(r'foiling-plates', FoilingPlateViewSet)
router.register(r'foiling-plate-products', FoilingPlateProductViewSet)
router.register(r'embossing-plates', EmbossingPlateViewSet)
router.register(r'embossing-plate-products', EmbossingPlateProductViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/user/', get_current_user, name='current-user'),
    path('auth/register/', register_view, name='register'),
    path('auth/salespersons/', get_salespersons, name='salespersons'),
    path('auth/users/', get_users_by_department, name='users-by-department'),
]

