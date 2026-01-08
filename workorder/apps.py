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

