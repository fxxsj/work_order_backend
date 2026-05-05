"""审计日志 Admin。"""

from django.contrib import admin

from ..models import AuditLog, AuditLogExport, AuditLogSettings


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "action_type",
        "username",
        "object_repr",
        "ip_address",
    ]
    list_filter = ["action_type", "created_at", "content_type"]
    search_fields = ["username", "object_repr", "request_path", "ip_address"]
    readonly_fields = [
        "id",
        "action_type",
        "user",
        "username",
        "content_type",
        "object_id",
        "object_repr",
        "changes",
        "changed_fields",
        "ip_address",
        "user_agent",
        "request_method",
        "request_path",
        "extra_context",
        "created_at",
    ]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AuditLogExport)
class AuditLogExportAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "status",
        "record_count",
        "file_size",
        "created_at",
        "completed_at",
    ]
    list_filter = ["status", "created_at", "completed_at"]
    search_fields = ["user__username", "file_path", "error_message"]
    readonly_fields = ["id", "created_at", "completed_at"]
    autocomplete_fields = ["user"]
    ordering = ["-created_at"]


@admin.register(AuditLogSettings)
class AuditLogSettingsAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "enabled",
        "retention_days",
        "log_login",
        "log_export",
        "updated_at",
    ]
    readonly_fields = ["updated_at"]

    def has_add_permission(self, request):
        if AuditLogSettings.objects.exists():
            return False
        return super().has_add_permission(request)
