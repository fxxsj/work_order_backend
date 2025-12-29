from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomerViewSet, ProcessViewSet, MaterialViewSet,
    WorkOrderViewSet, WorkOrderProcessViewSet,
    WorkOrderMaterialViewSet, ProcessLogViewSet
)

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'processes', ProcessViewSet)
router.register(r'materials', MaterialViewSet)
router.register(r'workorders', WorkOrderViewSet)
router.register(r'workorder-processes', WorkOrderProcessViewSet)
router.register(r'workorder-materials', WorkOrderMaterialViewSet)
router.register(r'process-logs', ProcessLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

