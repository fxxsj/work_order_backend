from django.apps import AppConfig


class WorkorderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'workorder'
    verbose_name = '施工单管理'
    
    def ready(self):
        # 导入自定义用户管理
        import config.custom_user_admin
        # 导入信号处理器（实现自动计算数量功能）
        import workorder.signals
        # 导入缓存失效信号处理器
        import workorder.performance.cache_invalidation  # noqa
        # 注册审计日志信号
        from workorder.services.audit_log_service import register_audit_signals
        register_audit_signals(self)
