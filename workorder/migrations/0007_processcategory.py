# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0006_remove_product_post_processing_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProcessCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True, verbose_name='分类名称')),
                ('code', models.CharField(max_length=20, unique=True, verbose_name='分类编码')),
                ('sort_order', models.IntegerField(default=0, verbose_name='排序')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '工序分类',
                'verbose_name_plural': '工序分类管理',
                'ordering': ['sort_order', 'code'],
            },
        ),
    ]

