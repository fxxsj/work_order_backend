from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("workorder", "0013_backfill_material_modes"),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="is_temporary",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="由物料规划自动生成，仅供对应施工单采购和库存追溯",
                verbose_name="施工单专用规格",
            ),
        ),
        migrations.AddField(
            model_name="material",
            name="temporary_for_work_order_material",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="temporary_purchase_specification",
                to="workorder.workordermaterial",
                verbose_name="所属施工单物料",
            ),
        ),
    ]
