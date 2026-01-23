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
    TaskAssignmentRuleViewSet,
    SupplierViewSet, MaterialSupplierViewSet, PurchaseOrderViewSet, PurchaseOrderItemViewSet,
    PurchaseReceiveRecordViewSet,
    SalesOrderViewSet, SalesOrderItemViewSet,
    # 财务视图集
    CostCenterViewSet, CostItemViewSet, ProductionCostViewSet,
    InvoiceViewSet, PaymentViewSet, PaymentPlanViewSet, StatementViewSet,
    # 库存视图集
    ProductStockViewSet, StockInViewSet, StockOutViewSet,
    DeliveryOrderViewSet, DeliveryItemViewSet, QualityInspectionViewSet,
)
# TODO: 多级审批功能待恢复（等待模型迁移完成）
# 暂时注释掉有问题的导入，避免自动重载错误
# 恢复步骤：
# 1. 取消注释下面的导入语句
# 2. 取消注释下面的路由注册（第85-94行附近）
# 3. 运行数据库迁移: python manage.py migrate
# 4. 测试多级审批功能是否正常
# 相关 issue: #XXX
#
from .views.multi_level_approval import (
    ApprovalWorkflowViewSet, ApprovalStepViewSet, MultiLevelApprovalViewSet,
    UrgentOrderViewSet, ApprovalReportViewSet
)
from .views.notification import (
    NotificationViewSet, SystemNotificationViewSet,
    UserNotificationSettingsViewSet, NotificationTemplateViewSet
)
from .auth_views import (
    LoginView, logout_view, get_current_user, register_view,
    get_salespersons, get_users_by_department, change_password, update_profile
)

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
router.register(r'purchase-receive-records', PurchaseReceiveRecordViewSet)
router.register(r'sales-orders', SalesOrderViewSet)
router.register(r'sales-order-items', SalesOrderItemViewSet)
router.register(r'workorders', WorkOrderViewSet)
router.register(r'workorder-processes', WorkOrderProcessViewSet)
router.register(r'workorder-products', WorkOrderProductViewSet)
router.register(r'workorder-materials', WorkOrderMaterialViewSet)
router.register(r'workorder-tasks', WorkOrderTaskViewSet)
router.register(r'product-groups', ProductGroupViewSet)
router.register(r'product-group-items', ProductGroupItemViewSet)
router.register(r'process-logs', ProcessLogViewSet)
router.register(r'task-assignment-rules', TaskAssignmentRuleViewSet)
router.register(r'notifications', NotificationViewSet, basename='notifications')
router.register(r'artworks', ArtworkViewSet)
router.register(r'artwork-products', ArtworkProductViewSet)
router.register(r'dies', DieViewSet)
router.register(r'die-products', DieProductViewSet)
router.register(r'foiling-plates', FoilingPlateViewSet)
router.register(r'foiling-plate-products', FoilingPlateProductViewSet)
router.register(r'embossing-plates', EmbossingPlateViewSet)
router.register(r'embossing-plate-products', EmbossingPlateProductViewSet)

# 财务路由
router.register(r'cost-centers', CostCenterViewSet, basename='cost-center')
router.register(r'cost-items', CostItemViewSet, basename='cost-item')
router.register(r'production-costs', ProductionCostViewSet, basename='production-cost')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'payment-plans', PaymentPlanViewSet, basename='payment-plan')
router.register(r'statements', StatementViewSet, basename='statement')

# 库存路由
router.register(r'product-stocks', ProductStockViewSet, basename='product-stock')
router.register(r'stock-ins', StockInViewSet, basename='stock-in')
router.register(r'stock-outs', StockOutViewSet, basename='stock-out')
router.register(r'delivery-orders', DeliveryOrderViewSet, basename='delivery-order')
router.register(r'delivery-items', DeliveryItemViewSet, basename='delivery-item')
router.register(r'quality-inspections', QualityInspectionViewSet, basename='quality-inspection')

# TODO: 多级审批功能待恢复（见上方第22-30行的详细说明）
# 暂时注释掉有问题的路由注册，直到模型迁移完成
router.register(r'approval-workflows', ApprovalWorkflowViewSet)
router.register(r'approval-steps', ApprovalStepViewSet)
router.register(r'multi-level-approval', MultiLevelApprovalViewSet, basename='multi-level-approval')
router.register(r'urgent-orders', UrgentOrderViewSet, basename='urgent-orders')
router.register(r'approval-reports', ApprovalReportViewSet, basename='approval-reports')
router.register(r'system-notifications', SystemNotificationViewSet, basename='system-notifications')
router.register(r'user-notification-settings', UserNotificationSettingsViewSet, basename='user-notification-settings')
router.register(r'notification-templates', NotificationTemplateViewSet, basename='notification-templates')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/user/', get_current_user, name='current-user'),
    path('auth/register/', register_view, name='register'),
    path('auth/salespersons/', get_salespersons, name='salespersons'),
    path('auth/users/', get_users_by_department, name='users-by-department'),
    path('auth/change-password/', change_password, name='change-password'),
    path('auth/update-profile/', update_profile, name='update-profile'),
]

