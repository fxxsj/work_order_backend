import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workorder", "0046_systemnotificationsettings_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workorder",
            name="customer",
            field=models.ForeignKey(
                help_text="销售订单客户快照，创建施工单时自动复制，请勿手动修改",
                on_delete=models.PROTECT,
                to="workorder.customer",
                verbose_name="客户",
            ),
        ),
        migrations.AlterField(
            model_name="workorder",
            name="order_date",
            field=models.DateField(
                default=datetime.date.today,
                help_text="销售订单日期快照，创建施工单时自动复制，请勿手动修改",
                verbose_name="下单日期",
            ),
        ),
        migrations.AlterField(
            model_name="workorder",
            name="delivery_date",
            field=models.DateField(
                help_text="销售订单交期快照，创建施工单时自动复制，请勿手动修改",
                verbose_name="交货日期",
            ),
        ),
        migrations.AlterField(
            model_name="workorder",
            name="total_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="销售订单金额快照，创建施工单时自动复制，请勿手动修改",
                max_digits=12,
                verbose_name="总金额",
            ),
        ),
    ]
