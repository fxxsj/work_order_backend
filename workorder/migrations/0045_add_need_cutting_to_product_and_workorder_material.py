# Generated manually for adding need_cutting field to ProductMaterial and WorkOrderMaterial

from django.db import migrations, models


def set_default_need_cutting_productmaterial(apps, schema_editor):
    """为现有的 ProductMaterial 记录设置默认的 need_cutting 值"""
    ProductMaterial = apps.get_model('workorder', 'ProductMaterial')
    ProductMaterial.objects.all().update(need_cutting=False)


def set_default_need_cutting_workordermaterial(apps, schema_editor):
    """为现有的 WorkOrderMaterial 记录设置默认的 need_cutting 值"""
    WorkOrderMaterial = apps.get_model('workorder', 'WorkOrderMaterial')
    WorkOrderMaterial.objects.all().update(need_cutting=False)


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0044_add_die_type_to_workorder'),
    ]

    operations = [
        migrations.AddField(
            model_name='productmaterial',
            name='need_cutting',
            field=models.BooleanField(
                default=False,
                help_text='该物料是否需要开料工序处理',
                verbose_name='需要开料'
            ),
        ),
        migrations.AddField(
            model_name='productmaterial',
            name='notes',
            field=models.TextField(
                blank=True,
                verbose_name='备注'
            ),
        ),
        migrations.AddField(
            model_name='workordermaterial',
            name='need_cutting',
            field=models.BooleanField(
                default=False,
                help_text='该物料是否需要开料工序处理',
                verbose_name='需要开料'
            ),
        ),
        # 为现有记录设置默认值
        migrations.RunPython(set_default_need_cutting_productmaterial, migrations.RunPython.noop),
        migrations.RunPython(set_default_need_cutting_workordermaterial, migrations.RunPython.noop),
    ]

