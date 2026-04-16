from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workorder", "0043_add_asset_images"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorder",
            name="contract_number",
            field=models.CharField(blank=True, max_length=100, verbose_name="合同号"),
        ),
    ]
