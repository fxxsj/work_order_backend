# Generated migration - Load initial categories

from django.db import migrations


def load_categories(apps, schema_editor):
    ProcessCategory = apps.get_model('workorder', 'ProcessCategory')
    
    categories = [
        {'id': 1, 'name': '印前', 'code': 'prepress', 'sort_order': 1},
        {'id': 2, 'name': '印刷', 'code': 'printing', 'sort_order': 2},
        {'id': 3, 'name': '表面处理', 'code': 'surface', 'sort_order': 3},
        {'id': 4, 'name': '后道加工', 'code': 'postpress', 'sort_order': 4},
        {'id': 5, 'name': '复合/裱合', 'code': 'laminating', 'sort_order': 5},
        {'id': 6, 'name': '成型/包装', 'code': 'forming', 'sort_order': 6},
        {'id': 7, 'name': '其他', 'code': 'other', 'sort_order': 99},
    ]
    
    for cat in categories:
        ProcessCategory.objects.create(**cat)


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0007_processcategory'),
    ]

    operations = [
        migrations.RunPython(load_categories),
    ]

