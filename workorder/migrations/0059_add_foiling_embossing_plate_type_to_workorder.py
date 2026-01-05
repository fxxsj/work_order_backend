# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0058_add_foiling_embossing_plates_to_workorder'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='foiling_plate_type',
            field=models.CharField(
                choices=[('no_foiling_plate', '不需要烫金版'), ('need_foiling_plate', '需要烫金版')],
                default='no_foiling_plate',
                help_text='是否需要烫金版',
                max_length=30,
                verbose_name='烫金版'
            ),
        ),
        migrations.AddField(
            model_name='workorder',
            name='embossing_plate_type',
            field=models.CharField(
                choices=[('no_embossing_plate', '不需要压凸版'), ('need_embossing_plate', '需要压凸版')],
                default='no_embossing_plate',
                help_text='是否需要压凸版',
                max_length=30,
                verbose_name='压凸版'
            ),
        ),
    ]

