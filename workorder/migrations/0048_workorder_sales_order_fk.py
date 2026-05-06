from django.db import migrations, models
import django.db.models.deletion


def backfill_workorder_sales_order(apps, schema_editor):
    WorkOrder = apps.get_model("workorder", "WorkOrder")
    SalesOrder = apps.get_model("workorder", "SalesOrder")
    through_model = SalesOrder.work_orders.through

    work_order_to_sales_order = {}
    for relation in through_model.objects.all().order_by("salesorder_id", "workorder_id"):
        work_order_to_sales_order.setdefault(relation.workorder_id, relation.salesorder_id)

    for work_order in WorkOrder.objects.all().only("id", "sales_order_id"):
        sales_order_id = work_order_to_sales_order.get(work_order.id)
        if sales_order_id and work_order.sales_order_id != sales_order_id:
            work_order.sales_order_id = sales_order_id
            work_order.save(update_fields=["sales_order"])


class Migration(migrations.Migration):

    dependencies = [
        ("workorder", "0047_workorder_snapshot_help_texts"),
    ]

    operations = [
        migrations.AddField(
            model_name="workorder",
            name="sales_order",
            field=models.ForeignKey(
                blank=True,
                help_text="施工单来源的客户订单。过渡期保留，与原关联施工单多对多并存。",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="source_work_orders",
                to="workorder.salesorder",
                verbose_name="来源客户订单",
            ),
        ),
        migrations.RunPython(
            backfill_workorder_sales_order,
            migrations.RunPython.noop,
        ),
    ]
