# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0057_add_foiling_type_to_foiling_plate'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='foiling_plates',
            field=models.ManyToManyField(
                blank=True,
                help_text='关联的烫金版，用于烫金工序，支持多个烫金版',
                related_name='work_orders',
                to='workorder.foilingplate',
                verbose_name='烫金版'
            ),
        ),
        migrations.AddField(
            model_name='workorder',
            name='embossing_plates',
            field=models.ManyToManyField(
                blank=True,
                help_text='关联的压凸版，用于压凸工序，支持多个压凸版',
                related_name='work_orders',
                to='workorder.embossingplate',
                verbose_name='压凸版'
            ),
        ),
    ]

