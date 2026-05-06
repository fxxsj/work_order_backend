from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("workorder", "0048_workorder_sales_order_fk"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="salesorder",
            name="work_orders",
        ),
    ]
