# Generated manually - Remove specification field from WorkOrder

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0046_remove_legacy_product_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='workorder',
            name='specification',
        ),
    ]

