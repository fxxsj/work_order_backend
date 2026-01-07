# Generated manually to configure process plate requirements

from django.db import migrations


def configure_process_plate_requirements_forward(apps, schema_editor):
    """配置工序的版需求字段"""
    Process = apps.get_model('workorder', 'Process')
    
    # 印刷工序：需要图稿
    Process.objects.filter(code='PRT').update(
        requires_artwork=True,
        artwork_required=True
    )
    
    # 模切工序：需要刀模
    Process.objects.filter(code='DIE').update(
        requires_die=True,
        die_required=True
    )
    
    # 烫金工序：需要烫金版
    Process.objects.filter(code='FOIL_G').update(
        requires_foiling_plate=True,
        foiling_plate_required=True
    )
    
    # 烫银工序：需要烫金版（使用同样的烫金版模型）
    Process.objects.filter(code='FOIL_S').update(
        requires_foiling_plate=True,
        foiling_plate_required=True
    )
    
    # 压凸工序：需要压凸版
    Process.objects.filter(code='EMB').update(
        requires_embossing_plate=True,
        embossing_plate_required=True
    )


def configure_process_plate_requirements_backward(apps, schema_editor):
    """回滚迁移：重置工序的版需求字段为默认值"""
    Process = apps.get_model('workorder', 'Process')
    
    # 重置所有相关字段为默认值 False
    Process.objects.filter(code='PRT').update(
        requires_artwork=False,
        artwork_required=True  # 默认值就是 True，但这里明确设置
    )
    
    Process.objects.filter(code='DIE').update(
        requires_die=False,
        die_required=True
    )
    
    Process.objects.filter(code='FOIL_G').update(
        requires_foiling_plate=False,
        foiling_plate_required=True
    )
    
    Process.objects.filter(code='FOIL_S').update(
        requires_foiling_plate=False,
        foiling_plate_required=True
    )
    
    Process.objects.filter(code='EMB').update(
        requires_embossing_plate=False,
        embossing_plate_required=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0006_add_task_assignment_fields'),
    ]

    operations = [
        migrations.RunPython(
            configure_process_plate_requirements_forward,
            configure_process_plate_requirements_backward
        ),
    ]

