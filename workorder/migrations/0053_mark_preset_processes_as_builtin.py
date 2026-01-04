# Generated manually - Mark preset processes as builtin

from django.db import migrations


def mark_preset_processes_as_builtin(apps, schema_editor):
    """将预设的21个工序标记为内置"""
    Process = apps.get_model('workorder', 'Process')
    
    # 预设工序的编码列表
    preset_codes = [
        'CTP', 'CUT', 'PRT', 'VAN', 'LAM_G', 'LAM_M', 'UV', 'FOIL_G', 'FOIL_S',
        'EMB', 'TEX', 'SCORE', 'DIE', 'TRIM', 'LAM_B', 'MOUNT', 'GLUE', 'BOX',
        'WINDOW', 'STAPLE', 'PACK'
    ]
    
    # 将这些工序标记为内置
    Process.objects.filter(code__in=preset_codes).update(is_builtin=True)


def mark_preset_processes_as_builtin_backward(apps, schema_editor):
    """回滚：取消内置标记"""
    Process = apps.get_model('workorder', 'Process')
    
    preset_codes = [
        'CTP', 'CUT', 'PRT', 'VAN', 'LAM_G', 'LAM_M', 'UV', 'FOIL_G', 'FOIL_S',
        'EMB', 'TEX', 'SCORE', 'DIE', 'TRIM', 'LAM_B', 'MOUNT', 'GLUE', 'BOX',
        'WINDOW', 'STAPLE', 'PACK'
    ]
    
    Process.objects.filter(code__in=preset_codes).update(is_builtin=False)


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0052_add_is_builtin_to_process'),
    ]

    operations = [
        migrations.RunPython(mark_preset_processes_as_builtin, mark_preset_processes_as_builtin_backward),
    ]

