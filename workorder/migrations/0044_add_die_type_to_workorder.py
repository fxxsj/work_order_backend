# Generated manually for die type selection

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0043_add_artwork_type_to_workorder'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='die_type',
            field=models.CharField(
                choices=[
                    ('no_die', '不需要刀模'),
                    ('new_design', '新设计刀模'),
                    ('need_update', '需更新刀模'),
                    ('old_die', '旧刀模'),
                ],
                default='no_die',
                help_text='刀模类型选择',
                max_length=20,
                verbose_name='刀模'
            ),
        ),
    ]

