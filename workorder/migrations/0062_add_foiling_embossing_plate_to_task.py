# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0061_configure_process_plate_relations'),
    ]

    operations = [
        migrations.AddField(
            model_name='workordertask',
            name='foiling_plate',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tasks',
                to='workorder.foilingplate',
                verbose_name='关联烫金版'
            ),
        ),
        migrations.AddField(
            model_name='workordertask',
            name='embossing_plate',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tasks',
                to='workorder.embossingplate',
                verbose_name='关联压凸版'
            ),
        ),
    ]

