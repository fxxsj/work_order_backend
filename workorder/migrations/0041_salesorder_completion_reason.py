from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workorder", "0040_seed_english_groups"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorder",
            name="completion_reason",
            field=models.TextField(
                blank=True,
                help_text="订单未全部发货但需要人工完结时填写原因",
                verbose_name="人工完结原因",
            ),
        ),
    ]
