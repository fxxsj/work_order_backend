from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workorder", "0014_material_temporary_specification"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productmaterial",
            name="calculation_mode",
            field=models.CharField(
                choices=[
                    ("fixed", "固定/直接填写"),
                    ("sheet_imposition", "拼版后算纸"),
                    ("specification_selection", "待规格确认"),
                ],
                default="fixed",
                max_length=30,
                verbose_name="需求计算方式",
            ),
        ),
        migrations.AlterField(
            model_name="productmaterial",
            name="preparation_mode",
            field=models.CharField(
                choices=[
                    ("pending", "待决定"),
                    ("direct", "直接领用/采购"),
                    ("internal_cutting", "厂内开料"),
                    ("supplier_cutting", "供应商按尺寸供货"),
                ],
                default="direct",
                max_length=30,
                verbose_name="备料方式",
            ),
        ),
        migrations.AlterField(
            model_name="workordermaterial",
            name="calculation_mode",
            field=models.CharField(
                choices=[
                    ("fixed", "固定/直接填写"),
                    ("sheet_imposition", "拼版后算纸"),
                    ("specification_selection", "待规格确认"),
                ],
                default="fixed",
                max_length=30,
                verbose_name="需求计算方式",
            ),
        ),
        migrations.AlterField(
            model_name="workordermaterial",
            name="preparation_mode",
            field=models.CharField(
                choices=[
                    ("pending", "待决定"),
                    ("direct", "直接领用/采购"),
                    ("internal_cutting", "厂内开料"),
                    ("supplier_cutting", "供应商按尺寸供货"),
                ],
                default="direct",
                max_length=30,
                verbose_name="备料方式",
            ),
        ),
        migrations.AddField(
            model_name="workordermaterial",
            name="planned_material_quantity",
            field=models.DecimalField(
                decimal_places=3,
                default=0,
                help_text="非纸物料规格确认后的计划需求量",
                max_digits=12,
                verbose_name="计划物料数量",
            ),
        ),
    ]
