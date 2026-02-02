"""
ASGI config for work order tracking system.

This application handles both HTTP and WebSocket protocols using Channels.
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# 初始化 Django (必须在导入路由之前)
django.setup()

# 现在可以安全导入路由
from workorder.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        URLRouter(websocket_urlpatterns)
        # 注意：认证在 NotificationConsumer 内部手动处理（从查询参数提取 token）
    ),
})
