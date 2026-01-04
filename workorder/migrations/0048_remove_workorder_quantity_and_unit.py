# Generated manually - Remove quantity and unit fields from WorkOrder

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0047_remove_workorder_specification'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='workorder',
            name='quantity',
        ),
        migrations.RemoveField(
            model_name='workorder',
            name='unit',
        ),
    ]

