# Generated migration - Change category to ForeignKey

from django.db import migrations, models
import django.db.models.deletion


def migrate_category_data(apps, schema_editor):
    Process = apps.get_model('workorder', 'Process')
    ProcessCategory = apps.get_model('workorder', 'ProcessCategory')
    
    # 映射关系
    category_map = {
        'prepress': ProcessCategory.objects.get(code='prepress'),
        'printing': ProcessCategory.objects.get(code='printing'),
        'surface': ProcessCategory.objects.get(code='surface'),
        'postpress': ProcessCategory.objects.get(code='postpress'),
        'laminating': ProcessCategory.objects.get(code='laminating'),
        'forming': ProcessCategory.objects.get(code='forming'),
        'other': ProcessCategory.objects.get(code='other'),
    }
    
    # 更新所有工序
    for process in Process.objects.all():
        if process.category_temp in category_map:
            process.category_new = category_map[process.category_temp]
            process.save()


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0009_process_category_temp'),
    ]

    operations = [
        # 添加新的外键字段（允许null）
        migrations.AddField(
            model_name='process',
            name='category_new',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                   related_name='processes_new', to='workorder.processcategory',
                                   verbose_name='工序分类'),
        ),
        # 迁移数据
        migrations.RunPython(migrate_category_data),
        # 删除旧的category字段
        migrations.RemoveField(
            model_name='process',
            name='category',
        ),
        # 删除临时字段
        migrations.RemoveField(
            model_name='process',
            name='category_temp',
        ),
        # 重命名新字段为category
        migrations.RenameField(
            model_name='process',
            old_name='category_new',
            new_name='category',
        ),
        # 设置为必填
        migrations.AlterField(
            model_name='process',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                   related_name='processes', to='workorder.processcategory',
                                   verbose_name='工序分类'),
        ),
    ]

