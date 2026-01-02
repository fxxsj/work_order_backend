# Generated manually

from django.db import migrations, models
import json


def convert_other_colors_to_json(apps, schema_editor):
    """将Text格式的other_colors转换为JSON数组"""
    Artwork = apps.get_model('workorder', 'Artwork')
    for artwork in Artwork.objects.all():
        if artwork.other_colors:
            # 如果是字符串，转换为数组
            if isinstance(artwork.other_colors, str):
                # 按逗号分隔，过滤空值
                colors = [c.strip() for c in artwork.other_colors.split(',') if c.strip()]
                artwork.other_colors = json.dumps(colors) if colors else []
            # 如果已经是列表，转换为JSON字符串
            elif isinstance(artwork.other_colors, list):
                artwork.other_colors = json.dumps(artwork.other_colors)
            artwork.save(update_fields=['other_colors'])
        else:
            # 空值设置为空数组的JSON
            artwork.other_colors = json.dumps([])
            artwork.save(update_fields=['other_colors'])


def reverse_convert_other_colors_to_text(apps, schema_editor):
    """将JSON数组转换回Text格式（用于回滚）"""
    Artwork = apps.get_model('workorder', 'Artwork')
    for artwork in Artwork.objects.all():
        if artwork.other_colors:
            # 如果是JSON字符串，解析为数组
            if isinstance(artwork.other_colors, str):
                try:
                    colors = json.loads(artwork.other_colors)
                    if isinstance(colors, list):
                        artwork.other_colors = ','.join(colors)
                    else:
                        artwork.other_colors = ''
                except (json.JSONDecodeError, TypeError):
                    artwork.other_colors = ''
            # 如果已经是列表，转换为逗号分隔的字符串
            elif isinstance(artwork.other_colors, list):
                artwork.other_colors = ','.join(artwork.other_colors)
            artwork.save(update_fields=['other_colors'])
        else:
            artwork.other_colors = ''
            artwork.save(update_fields=['other_colors'])


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0036_change_artwork_color_count_to_cmyk_and_other'),
    ]

    operations = [
        # 先转换数据
        migrations.RunPython(convert_other_colors_to_json, reverse_convert_other_colors_to_text),
        # 再改变字段类型
        migrations.AlterField(
            model_name='artwork',
            name='other_colors',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='其他颜色列表，如：["528C", "金色"]',
                verbose_name='其他颜色'
            ),
        ),
    ]

