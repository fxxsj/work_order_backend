"""
WebSocket路由配置

处理实时通知的WebSocket连接
"""

from django.urls import re_path
from .services.realtime_notification import NotificationConsumer

websocket_urlpatterns = [
    re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
]