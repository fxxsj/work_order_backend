# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0056_add_foiling_embossing_plates_to_artwork'),
    ]

    operations = [
        migrations.AddField(
            model_name='foilingplate',
            name='foiling_type',
            field=models.CharField(
                choices=[('gold', '烫金'), ('silver', '烫银')],
                default='gold',
                help_text='该版是烫金还是烫银',
                max_length=20,
                verbose_name='类型'
            ),
        ),
    ]

