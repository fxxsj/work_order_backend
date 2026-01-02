# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0035_add_printing_type_to_workorder'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='artwork',
            name='color_count',
        ),
        migrations.AddField(
            model_name='artwork',
            name='cmyk_colors',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='选中的CMYK颜色，如：["C", "M", "K"]',
                verbose_name='CMYK颜色'
            ),
        ),
        migrations.AddField(
            model_name='artwork',
            name='other_colors',
            field=models.TextField(
                blank=True,
                help_text='其他颜色，多个颜色用逗号分隔，如：528C,金色',
                verbose_name='其他颜色'
            ),
        ),
    ]

