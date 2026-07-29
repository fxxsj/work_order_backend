# Generated for 统一 SalesOrder status 语义（审批通过后 status: pending → approved）

from django.db import migrations


def forward(apps, schema_editor):
    """历史数据回填：审批已通过但 status 仍为 pending 的订单推进为 approved。

    修复根因：此前 ApprovalService.approve 只改 approval_status 不改 status，
    导致审批通过后 status 停留在 pending，无法创建施工单。
    """
    SalesOrder = apps.get_model("workorder", "SalesOrder")
    db_alias = schema_editor.connection.alias
    SalesOrder.objects.using(db_alias).filter(
        approval_status="approved", status="pending"
    ).update(status="approved")


def reverse(apps, schema_editor):
    SalesOrder = apps.get_model("workorder", "SalesOrder")
    db_alias = schema_editor.connection.alias
    SalesOrder.objects.using(db_alias).filter(
        approval_status="approved", status="approved"
    ).update(status="pending")


class Migration(migrations.Migration):

    dependencies = [
        ("workorder", "0017_product_customer_relation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="salesorder",
            name="status",
            field=__import__("django.db.models", fromlist=["models"]).CharField(
                choices=[
                    ("pending", "待处理"),
                    ("approved", "已审核"),
                    ("in_production", "生产中"),
                    ("completed", "已完成"),
                    ("cancelled", "已取消"),
                ],
                default="pending",
                max_length=20,
                verbose_name="订单状态",
            ),
        ),
        migrations.RunPython(forward, reverse_code=reverse),
    ]
