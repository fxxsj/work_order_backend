# Generated migration to migrate artwork data from ForeignKey to ManyToMany

from django.db import migrations


def migrate_artwork_data(apps, schema_editor):
    """将单个 artwork 数据迁移到 artworks ManyToMany 字段"""
    WorkOrder = apps.get_model('workorder', 'WorkOrder')
    Artwork = apps.get_model('workorder', 'Artwork')
    
    # 遍历所有施工单，将 artwork 添加到 artworks
    for work_order in WorkOrder.objects.all():
        # 通过旧字段获取 artwork_id（如果存在）
        # 注意：在迁移时，artwork 字段可能已经被删除，所以需要通过原始 SQL 或保存的 ID 来获取
        # 由于 Django 迁移的顺序，artwork 字段在此时应该还存在
        if hasattr(work_order, 'artwork') and work_order.artwork:
            work_order.artworks.add(work_order.artwork)


def reverse_migrate_artwork_data(apps, schema_editor):
    """反向迁移：将 artworks 的第一个图稿设置回 artwork 字段"""
    WorkOrder = apps.get_model('workorder', 'WorkOrder')
    
    for work_order in WorkOrder.objects.all():
        if work_order.artworks.exists():
            # 将第一个图稿设置回 artwork 字段（如果字段还存在）
            first_artwork = work_order.artworks.first()
            if hasattr(work_order, 'artwork'):
                work_order.artwork = first_artwork
                work_order.save()


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0027_change_artwork_to_manytomany'),
    ]

    operations = [
        migrations.RunPython(migrate_artwork_data, reverse_migrate_artwork_data),
    ]

