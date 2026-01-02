# Generated manually

from django.db import migrations, models
import json


def migrate_printing_colors_forward(apps, schema_editor):
    """将 printing_colors 字符串转换为 printing_cmyk_colors 和 printing_other_colors"""
    WorkOrder = apps.get_model('workorder', 'WorkOrder')
    
    for work_order in WorkOrder.objects.all():
        # 如果 printing_colors 为空，跳过
        if not work_order.printing_colors:
            work_order.printing_cmyk_colors = []
            work_order.printing_other_colors = []
            work_order.save()
            continue
        
        # 尝试解析 printing_colors（可能是逗号分隔的字符串）
        colors_str = work_order.printing_colors.strip()
        if not colors_str:
            work_order.printing_cmyk_colors = []
            work_order.printing_other_colors = []
            work_order.save()
            continue
        
        # 简单的解析逻辑：如果包含 CMYK 字符，提取它们
        cmyk_colors = []
        other_colors = []
        
        # 检查是否包含 CMYK 字符
        for char in ['C', 'M', 'Y', 'K']:
            if char in colors_str:
                cmyk_colors.append(char)
        
        # 如果还有非 CMYK 的内容，作为其他颜色
        # 这里简化处理，将整个字符串作为其他颜色（如果包含非 CMYK 字符）
        # 实际使用中，用户会重新编辑，所以这里只是迁移数据
        if colors_str and not all(c in ['C', 'M', 'Y', 'K', ' ', ',', '（', '）', '+'] for c in colors_str):
            # 尝试提取其他颜色（简单处理）
            parts = colors_str.replace('+', ',').split(',')
            for part in parts:
                part = part.strip()
                if part and part not in ['C', 'M', 'Y', 'K'] and not part.startswith('（') and not part.endswith('色）'):
                    other_colors.append(part)
        
        work_order.printing_cmyk_colors = cmyk_colors
        work_order.printing_other_colors = other_colors
        work_order.save()


def migrate_printing_colors_backward(apps, schema_editor):
    """反向迁移：将 printing_cmyk_colors 和 printing_other_colors 合并为 printing_colors"""
    WorkOrder = apps.get_model('workorder', 'WorkOrder')
    
    for work_order in WorkOrder.objects.all():
        parts = []
        
        # CMYK颜色
        if work_order.printing_cmyk_colors:
            cmyk_order = ['C', 'M', 'Y', 'K']
            cmyk_sorted = [c for c in cmyk_order if c in work_order.printing_cmyk_colors]
            if cmyk_sorted:
                parts.append(''.join(cmyk_sorted))
        
        # 其他颜色
        if work_order.printing_other_colors:
            other_colors_str = ','.join(work_order.printing_other_colors)
            if other_colors_str:
                parts.append(other_colors_str)
        
        # 组合显示
        if len(parts) > 1:
            work_order.printing_colors = '+'.join(parts)
        elif len(parts) == 1:
            work_order.printing_colors = parts[0]
        else:
            work_order.printing_colors = ''
        
        work_order.save()


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0038_add_printing_colors_to_workorder'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='printing_cmyk_colors',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='选中的CMYK颜色，如：["C", "M", "K"]',
                verbose_name='印刷CMYK颜色'
            ),
        ),
        migrations.AddField(
            model_name='workorder',
            name='printing_other_colors',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='其他颜色列表，如：["528C", "金色"]',
                verbose_name='印刷其他颜色'
            ),
        ),
        migrations.RunPython(
            migrate_printing_colors_forward,
            migrate_printing_colors_backward
        ),
        migrations.RemoveField(
            model_name='workorder',
            name='printing_colors',
        ),
    ]

