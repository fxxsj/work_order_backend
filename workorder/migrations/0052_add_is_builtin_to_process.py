# Generated manually - Add is_builtin field to Process

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0051_load_preset_processes'),
    ]

    operations = [
        migrations.AddField(
            model_name='process',
            name='is_builtin',
            field=models.BooleanField(default=False, help_text='内置工序不可删除，code字段不可编辑', verbose_name='是否内置'),
        ),
    ]

