# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0034_remove_imposition_quantity_from_workorder'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='printing_type',
            field=models.CharField(
                choices=[
                    ('none', '不需要印刷'),
                    ('front', '正面印刷'),
                    ('back', '背面印刷'),
                    ('self_reverse', '自反印刷'),
                    ('reverse_gripper', '反咬口印刷'),
                    ('register', '套版印刷'),
                ],
                default='none',
                help_text='印刷形式，选择图稿时必选',
                max_length=20,
                verbose_name='印刷形式'
            ),
        ),
    ]

