# Generated manually on 2025-01-04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0054_add_foiling_plate'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmbossingPlate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(blank=True, max_length=50, unique=True, verbose_name='压凸版编码')),
                ('name', models.CharField(max_length=200, verbose_name='压凸版名称')),
                ('size', models.CharField(blank=True, help_text='如：420x594mm、889x1194mm等', max_length=100, verbose_name='尺寸')),
                ('material', models.CharField(blank=True, help_text='如：铜版、锌版等', max_length=100, verbose_name='材质')),
                ('thickness', models.CharField(blank=True, help_text='如：3mm、5mm等', max_length=50, verbose_name='厚度')),
                ('notes', models.TextField(blank=True, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '压凸版',
                'verbose_name_plural': '压凸版管理',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EmbossingPlateProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(default=1, help_text='该产品在压凸版中的数量', verbose_name='数量')),
                ('sort_order', models.IntegerField(default=0, verbose_name='排序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('embossing_plate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='workorder.embossingplate', verbose_name='压凸版')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='workorder.product', verbose_name='产品')),
            ],
            options={
                'verbose_name': '压凸版产品',
                'verbose_name_plural': '压凸版产品管理',
                'ordering': ['embossing_plate', 'sort_order'],
                'unique_together': {('embossing_plate', 'product')},
            },
        ),
    ]

