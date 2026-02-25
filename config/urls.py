"""
URL configuration for work order tracking system.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


def health_view(_request):
    checks = {}
    overall = "healthy"

    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover
        checks["database"] = f"error: {exc}"
        overall = "unhealthy"

    try:
        cache.set("health_check", "ok", 5)
        cache.get("health_check")
        checks["cache"] = "ok"
    except Exception as exc:  # pragma: no cover
        checks["cache"] = f"error: {exc}"
        if overall == "healthy":
            overall = "degraded"

    status_code = 200 if overall in ("healthy", "degraded") else 503
    return JsonResponse({"status": overall, "checks": checks}, status=status_code)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_view, name="health"),
    path("api/", include("workorder.urls")),
    # API documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Backward-compatible explicit OpenAPI JSON endpoint (some docs/tools expect this)
    path("api/openapi.json", SpectacularAPIView.as_view(), name="openapi-json"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Prometheus metrics (protect with authentication in production!)
    path("metrics/", include("django_prometheus.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = "印刷施工单跟踪系统"
admin.site.site_title = "印刷施工单管理"
admin.site.index_title = "欢迎使用印刷施工单跟踪系统"
