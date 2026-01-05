# Generated manually

from django.db import migrations


def configure_process_plate_relations(apps, schema_editor):
    """为现有工序配置版的关系"""
    Process = apps.get_model('workorder', 'Process')
    
    # 配置印刷工序：需要图稿，图稿必选
    Process.objects.filter(
        name__icontains='印刷'
    ).update(
        requires_artwork=True,
        artwork_required=True
    )
    
    # 配置模切工序：需要刀模，刀模必选
    Process.objects.filter(
        name__icontains='模切'
    ).update(
        requires_die=True,
        die_required=True
    )
    
    # 配置烫金工序：需要烫金版，烫金版必选
    Process.objects.filter(
        name__icontains='烫金'
    ).update(
        requires_foiling_plate=True,
        foiling_plate_required=True
    )
    
    # 配置烫银工序：需要烫金版，烫金版必选（烫银也是用烫金版）
    Process.objects.filter(
        name__icontains='烫银'
    ).update(
        requires_foiling_plate=True,
        foiling_plate_required=True
    )
    
    # 配置压凸工序：需要压凸版，压凸版必选
    Process.objects.filter(
        name__icontains='压凸'
    ).update(
        requires_embossing_plate=True,
        embossing_plate_required=True
    )
    
    # 配置制版工序：制版工序会根据版的选择自动勾选，不需要用户手动选择
    # 因此不需要配置 requires_* 字段，制版工序不会触发版选择项的显示
    # 但为了完整性，设置为都不需要（实际上不会用到，因为制版是自动选择的）
    Process.objects.filter(
        name__icontains='制版'
    ).update(
        requires_artwork=False,
        artwork_required=False,
        requires_die=False,
        die_required=False,
        requires_foiling_plate=False,
        foiling_plate_required=False,
        requires_embossing_plate=False,
        embossing_plate_required=False
    )


def reverse_configure_process_plate_relations(apps, schema_editor):
    """反向操作：清空所有工序的版关系配置"""
    Process = apps.get_model('workorder', 'Process')
    Process.objects.all().update(
        requires_artwork=False,
        artwork_required=True,
        requires_die=False,
        die_required=True,
        requires_foiling_plate=False,
        foiling_plate_required=True,
        requires_embossing_plate=False,
        embossing_plate_required=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0060_remove_plate_type_fields_add_process_plate_relations'),
    ]

    operations = [
        migrations.RunPython(
            configure_process_plate_relations,
            reverse_configure_process_plate_relations
        ),
    ]

