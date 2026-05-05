from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workorder", "0045_product_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="notification_preferences",
            field=models.JSONField(
                blank=True,
                default={
                    "email_notifications": True,
                    "websocket_notifications": True,
                    "task_assignments": True,
                    "process_completions": True,
                    "deadline_warnings": True,
                    "system_announcements": True,
                    "urgency_threshold": "normal",
                    "quiet_hours_enabled": False,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                },
                help_text="用户级通知开关、紧急阈值和免打扰时间段配置",
                verbose_name="通知偏好设置",
            ),
        ),
        migrations.CreateModel(
            name="SystemNotificationSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="创建时间"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="更新时间"),
                ),
                (
                    "singleton_key",
                    models.CharField(
                        default="default",
                        editable=False,
                        max_length=32,
                        unique=True,
                        verbose_name="单例键",
                    ),
                ),
                (
                    "websocket_enabled",
                    models.BooleanField(default=True, verbose_name="启用 WebSocket 通知"),
                ),
                (
                    "email_enabled",
                    models.BooleanField(default=True, verbose_name="启用邮件通知"),
                ),
                (
                    "sms_enabled",
                    models.BooleanField(default=False, verbose_name="启用短信通知"),
                ),
                (
                    "email_threshold",
                    models.CharField(
                        choices=[
                            ("low", "低"),
                            ("normal", "普通"),
                            ("high", "高"),
                            ("urgent", "紧急"),
                        ],
                        default="high",
                        max_length=10,
                        verbose_name="邮件发送阈值",
                    ),
                ),
                (
                    "notification_retention_days",
                    models.PositiveIntegerField(default=30, verbose_name="通知保留天数"),
                ),
                (
                    "auto_cleanup_enabled",
                    models.BooleanField(default=True, verbose_name="自动清理过期通知"),
                ),
                (
                    "max_notifications_per_user",
                    models.PositiveIntegerField(default=1000, verbose_name="单用户通知上限"),
                ),
            ],
            options={
                "verbose_name": "系统通知设置",
                "verbose_name_plural": "系统通知设置",
            },
        ),
        migrations.CreateModel(
            name="NotificationTemplate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="创建时间"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="更新时间"),
                ),
                ("key", models.CharField(max_length=50, unique=True, verbose_name="模板键")),
                ("title", models.CharField(max_length=200, verbose_name="标题模板")),
                ("message", models.TextField(verbose_name="内容模板")),
                ("variables", models.JSONField(blank=True, default=list, verbose_name="模板变量")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
            ],
            options={
                "verbose_name": "通知模板",
                "verbose_name_plural": "通知模板",
                "ordering": ["key"],
            },
        ),
    ]
