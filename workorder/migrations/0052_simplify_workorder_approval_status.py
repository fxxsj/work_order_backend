from django.db import migrations, models


def forwards(apps, schema_editor):
    WorkOrder = apps.get_model("workorder", "WorkOrder")
    WorkOrder.objects.filter(approval_status="pending").update(approval_status="submitted")


def backwards(apps, schema_editor):
    WorkOrder = apps.get_model("workorder", "WorkOrder")
    WorkOrder.objects.filter(approval_status__in=["draft", "submitted"]).update(
        approval_status="pending"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("workorder", "0051_add_process_snapshot_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workorder",
            name="approval_status",
            field=models.CharField(
                choices=[
                    ("draft", "草稿"),
                    ("submitted", "待审核"),
                    ("approved", "已通过"),
                    ("rejected", "已拒绝"),
                ],
                default="draft",
                max_length=20,
                verbose_name="审核状态",
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
