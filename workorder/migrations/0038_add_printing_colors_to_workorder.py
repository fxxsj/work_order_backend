# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0037_change_artwork_other_colors_to_jsonfield'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='printing_colors',
            field=models.CharField(
                blank=True,
                help_text='印刷色数，选择图稿后自动填充，可编辑',
                max_length=500,
                verbose_name='印刷色数'
            ),
        ),
    ]

