# Generated migration - Add temp category field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0008_load_categories'),
    ]

    operations = [
        # 添加临时字段存储旧的category值
        migrations.AddField(
            model_name='process',
            name='category_temp',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        # 复制旧值到临时字段
        migrations.RunSQL(
            "UPDATE workorder_process SET category_temp = category",
            migrations.RunSQL.noop
        ),
    ]

