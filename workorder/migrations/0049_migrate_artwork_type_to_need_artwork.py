# Generated manually - Migrate artwork_type from 4 options to 2 options

from django.db import migrations


def migrate_artwork_type_forward(apps, schema_editor):
    """将旧的 artwork_type 值迁移到新值"""
    WorkOrder = apps.get_model('workorder', 'WorkOrder')
    
    # 将 new_design, need_update, old_artwork 都迁移为 need_artwork
    WorkOrder.objects.filter(artwork_type__in=['new_design', 'need_update', 'old_artwork']).update(artwork_type='need_artwork')
    # no_artwork 保持不变


def migrate_artwork_type_backward(apps, schema_editor):
    """回滚迁移：将 need_artwork 迁移回 old_artwork（因为无法确定原始值）"""
    WorkOrder = apps.get_model('workorder', 'WorkOrder')
    
    # 回滚时，将 need_artwork 迁移为 old_artwork（保守选择）
    WorkOrder.objects.filter(artwork_type='need_artwork').update(artwork_type='old_artwork')


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0048_remove_workorder_quantity_and_unit'),
    ]

    operations = [
        migrations.RunPython(migrate_artwork_type_forward, migrate_artwork_type_backward),
    ]

