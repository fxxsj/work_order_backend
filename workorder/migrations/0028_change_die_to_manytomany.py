# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0027_change_artwork_to_manytomany'),
    ]

    operations = [
        # 第一步：添加新的 dies ManyToManyField（临时名称，避免冲突）
        migrations.AddField(
            model_name='workorder',
            name='dies',
            field=models.ManyToManyField(blank=True, related_name='work_orders', to='workorder.die', verbose_name='刀模'),
        ),
        # 第二步：迁移数据（从 die ForeignKey 到 dies ManyToMany）
        migrations.RunPython(
            code=lambda apps, schema_editor: migrate_die_data(apps, schema_editor),
            reverse_code=lambda apps, schema_editor: reverse_migrate_die_data(apps, schema_editor),
        ),
        # 第三步：删除旧的 die ForeignKey 字段
        migrations.RemoveField(
            model_name='workorder',
            name='die',
        ),
    ]


def migrate_die_data(apps, schema_editor):
    """将 die ForeignKey 数据迁移到 dies ManyToMany"""
    WorkOrder = apps.get_model('workorder', 'WorkOrder')
    for work_order in WorkOrder.objects.all():
        if work_order.die_id:  # 如果有关联的刀模
            work_order.dies.add(work_order.die_id)


def reverse_migrate_die_data(apps, schema_editor):
    """反向迁移：从 dies ManyToMany 恢复到 die ForeignKey（取第一个）"""
    WorkOrder = apps.get_model('workorder', 'WorkOrder')
    for work_order in WorkOrder.objects.all():
        dies = work_order.dies.all()
        if dies.exists():
            # 取第一个刀模作为 ForeignKey 值
            work_order.die_id = dies.first().id
            work_order.save()

