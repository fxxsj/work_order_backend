# Generated manually - Migrate die_type from 4 options to 2 options

from django.db import migrations


def migrate_die_type_forward(apps, schema_editor):
    """将旧的 die_type 值迁移到新值"""
    WorkOrder = apps.get_model('workorder', 'WorkOrder')
    
    # 将 new_design, need_update, old_die 都迁移为 need_die
    WorkOrder.objects.filter(die_type__in=['new_design', 'need_update', 'old_die']).update(die_type='need_die')
    # no_die 保持不变


def migrate_die_type_backward(apps, schema_editor):
    """回滚迁移：将 need_die 迁移回 old_die（因为无法确定原始值）"""
    WorkOrder = apps.get_model('workorder', 'WorkOrder')
    
    # 回滚时，将 need_die 迁移为 old_die（保守选择）
    WorkOrder.objects.filter(die_type='need_die').update(die_type='old_die')


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0049_migrate_artwork_type_to_need_artwork'),
    ]

    operations = [
        migrations.RunPython(migrate_die_type_forward, migrate_die_type_backward),
    ]

