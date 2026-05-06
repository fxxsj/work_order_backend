from django.db import migrations, models
import django.db.models.deletion


def backfill_workorderproduct_sources(apps, schema_editor):
    WorkOrderProduct = apps.get_model("workorder", "WorkOrderProduct")

    for item in WorkOrderProduct.objects.select_related("work_order").all():
        if item.work_order_id and getattr(item.work_order, "sales_order_id", None):
            item.source_type = "sales_order"
        else:
            item.source_type = "stock"
        item.save(update_fields=["source_type"])


class Migration(migrations.Migration):

    dependencies = [
        ("workorder", "0049_remove_salesorder_work_orders"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workorder",
            name="sales_order",
            field=models.ForeignKey(
                blank=True,
                help_text="施工单来源的客户订单，选择后会自动同步客户、下单日期、交货日期和金额快照。",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="source_work_orders",
                to="workorder.salesorder",
                verbose_name="来源客户订单",
            ),
        ),
        migrations.AddField(
            model_name="workorderproduct",
            name="sales_order_item",
            field=models.ForeignKey(
                blank=True,
                help_text="如果来源是客户订单，关联到具体订单明细，便于拼版追溯",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="work_order_products",
                to="workorder.salesorderitem",
                verbose_name="来源订单明细",
            ),
        ),
        migrations.AddField(
            model_name="workorderproduct",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("sales_order", "客户订单"),
                    ("stock", "库存生产"),
                    ("reprint", "补印"),
                    ("sample", "打样"),
                ],
                default="stock",
                help_text="该产品行来自客户订单、库存生产、补印或打样",
                max_length=20,
                verbose_name="来源类型",
            ),
        ),
        migrations.RunPython(
            backfill_workorderproduct_sources,
            migrations.RunPython.noop,
        ),
    ]
