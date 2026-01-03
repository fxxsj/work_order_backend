# Generated manually for artwork type selection

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0042_add_task_management_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='artwork_type',
            field=models.CharField(
                choices=[
                    ('no_artwork', '不需要图稿'),
                    ('new_design', '新设计图稿'),
                    ('need_update', '需更新图稿'),
                    ('old_artwork', '旧图稿'),
                ],
                default='no_artwork',
                help_text='图稿类型选择',
                max_length=20,
                verbose_name='图稿（CTP版）'
            ),
        ),
    ]

