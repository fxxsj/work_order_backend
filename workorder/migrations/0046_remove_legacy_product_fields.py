# Generated manually - Remove legacy product fields from WorkOrder

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0045_add_need_cutting_to_product_and_workorder_material'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='workorder',
            name='product',
        ),
        migrations.RemoveField(
            model_name='workorder',
            name='product_name',
        ),
    ]

