from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomerViewSet, ProcessCategoryViewSet, ProcessViewSet, ProductViewSet, MaterialViewSet,
    WorkOrderViewSet, WorkOrderProcessViewSet,
    WorkOrderMaterialViewSet, ProcessLogViewSet
)
from .auth_views import login_view, logout_view, get_current_user, register_view

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'process-categories', ProcessCategoryViewSet)
router.register(r'processes', ProcessViewSet)
router.register(r'products', ProductViewSet)
router.register(r'materials', MaterialViewSet)
router.register(r'workorders', WorkOrderViewSet)
router.register(r'workorder-processes', WorkOrderProcessViewSet)
router.register(r'workorder-materials', WorkOrderMaterialViewSet)
router.register(r'process-logs', ProcessLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/user/', get_current_user, name='current-user'),
    path('auth/register/', register_view, name='register'),
]

