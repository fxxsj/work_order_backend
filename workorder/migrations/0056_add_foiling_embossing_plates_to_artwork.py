# Generated manually on 2025-01-04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0055_add_embossing_plate'),
    ]

    operations = [
        migrations.AddField(
            model_name='artwork',
            name='foiling_plates',
            field=models.ManyToManyField(blank=True, help_text='该图稿关联的烫金版', related_name='artworks', to='workorder.foilingplate', verbose_name='关联烫金版'),
        ),
        migrations.AddField(
            model_name='artwork',
            name='embossing_plates',
            field=models.ManyToManyField(blank=True, help_text='该图稿关联的压凸版', related_name='artworks', to='workorder.embossingplate', verbose_name='关联压凸版'),
        ),
    ]

