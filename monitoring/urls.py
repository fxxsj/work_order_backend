"""
监控系统的URL配置
为性能监控系统提供API接口
"""
from django.urls import path
from . import performance_monitor as views

app_name = 'monitoring'

urlpatterns = [
    # 性能指标API
    path('metrics/system/', views.get_system_metrics, name='get_system_metrics'),
    path('metrics/database/', views.get_database_metrics, name='get_database_metrics'),
    path('metrics/application/', views.get_application_metrics, name='get_application_metrics'),
    path('metrics/business/', views.get_business_metrics, name='get_business_metrics'),
    
    # 告警API
    path('alerts/', views.get_alerts, name='get_alerts'),
]