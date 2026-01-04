# Generated manually - Load preset processes data

from django.db import migrations


def load_preset_processes_forward(apps, schema_editor):
    """加载预设的21个标准工序"""
    Process = apps.get_model('workorder', 'Process')
    
    # 检查是否已有数据，如果有则跳过
    if Process.objects.exists():
        return
    
    # 预设工序数据（标记为内置）
    processes_data = [
        {'code': 'CTP', 'name': '制版', 'description': 'CTP制版', 'standard_duration': 0, 'sort_order': 1, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'CUT', 'name': '开料', 'description': '材料开料', 'standard_duration': 0, 'sort_order': 2, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'PRT', 'name': '印刷', 'description': '印刷', 'standard_duration': 0, 'sort_order': 3, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'VAN', 'name': '过油', 'description': '过油', 'standard_duration': 0, 'sort_order': 4, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'LAM_G', 'name': '覆光膜', 'description': '覆光膜', 'standard_duration': 0, 'sort_order': 5, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'LAM_M', 'name': '覆哑膜', 'description': '覆哑膜', 'standard_duration': 0, 'sort_order': 6, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'UV', 'name': 'UV', 'description': 'UV工艺', 'standard_duration': 0, 'sort_order': 7, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'FOIL_G', 'name': '烫金', 'description': '烫金', 'standard_duration': 0, 'sort_order': 8, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'FOIL_S', 'name': '烫银', 'description': '烫银', 'standard_duration': 0, 'sort_order': 9, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'EMB', 'name': '压凸', 'description': '压凸', 'standard_duration': 0, 'sort_order': 10, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'TEX', 'name': '压纹', 'description': '压纹', 'standard_duration': 0, 'sort_order': 11, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'SCORE', 'name': '压线', 'description': '压线', 'standard_duration': 0, 'sort_order': 12, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'DIE', 'name': '模切', 'description': '模切', 'standard_duration': 0, 'sort_order': 13, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'TRIM', 'name': '切成品', 'description': '切成品', 'standard_duration': 0, 'sort_order': 14, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'LAM_B', 'name': '对裱', 'description': '对裱', 'standard_duration': 0, 'sort_order': 15, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'MOUNT', 'name': '裱坑', 'description': '裱坑', 'standard_duration': 0, 'sort_order': 16, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'GLUE', 'name': '粘胶', 'description': '粘胶', 'standard_duration': 0, 'sort_order': 17, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'BOX', 'name': '粘盒', 'description': '粘盒', 'standard_duration': 0, 'sort_order': 18, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'WINDOW', 'name': '粘窗口', 'description': '粘窗口', 'standard_duration': 0, 'sort_order': 19, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'STAPLE', 'name': '打钉', 'description': '打钉', 'standard_duration': 0, 'sort_order': 20, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
        {'code': 'PACK', 'name': '包装', 'description': '包装', 'standard_duration': 0, 'sort_order': 21, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general'},
    ]
    
    # 创建工序
    for process_data in processes_data:
        Process.objects.create(**process_data)


def load_preset_processes_backward(apps, schema_editor):
    """回滚迁移：删除预设工序"""
    Process = apps.get_model('workorder', 'Process')
    
    # 删除预设的21个工序（通过code匹配）
    preset_codes = [
        'CTP', 'CUT', 'PRT', 'VAN', 'LAM_G', 'LAM_M', 'UV', 'FOIL_G', 'FOIL_S',
        'EMB', 'TEX', 'SCORE', 'DIE', 'TRIM', 'LAM_B', 'MOUNT', 'GLUE', 'BOX',
        'WINDOW', 'STAPLE', 'PACK'
    ]
    Process.objects.filter(code__in=preset_codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0050_migrate_die_type_to_need_die'),
    ]

    operations = [
        migrations.RunPython(load_preset_processes_forward, load_preset_processes_backward),
    ]
