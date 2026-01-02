# Generated manually

from django.db import migrations, models


def migrate_artwork_code_to_base_code(apps, schema_editor):
    """将现有的 code 字段迁移到 base_code，并设置 version 为 1"""
    Artwork = apps.get_model('workorder', 'Artwork')
    
    for artwork in Artwork.objects.all():
        if artwork.code and not artwork.base_code:
            artwork.base_code = artwork.code
            artwork.version = 1
            artwork.save()


def reverse_migrate(apps, schema_editor):
    """反向迁移：将 base_code 和 version 合并回 code"""
    Artwork = apps.get_model('workorder', 'Artwork')
    
    for artwork in Artwork.objects.all():
        if artwork.base_code:
            if artwork.version > 1:
                artwork.code = f"{artwork.base_code}-v{artwork.version}"
            else:
                artwork.code = artwork.base_code
            artwork.save()


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0040_add_dies_to_artwork'),
    ]

    operations = [
        # 添加新字段
        migrations.AddField(
            model_name='artwork',
            name='base_code',
            field=models.CharField(
                blank=True,
                editable=False,
                help_text='图稿的主编码，如：ART202412001，不包含版本号',
                max_length=50,
                null=True,
                verbose_name='图稿主编码'
            ),
        ),
        migrations.AddField(
            model_name='artwork',
            name='version',
            field=models.IntegerField(
                default=1,
                help_text='图稿版本号，从1开始递增',
                verbose_name='版本号'
            ),
        ),
        # 迁移数据
        migrations.RunPython(
            migrate_artwork_code_to_base_code,
            reverse_migrate
        ),
        # 移除旧的唯一约束，添加新的组合唯一约束
        migrations.AlterUniqueTogether(
            name='artwork',
            unique_together={('base_code', 'version')},
        ),
        # 移除旧的 code 字段（不再需要）
        migrations.RemoveField(
            model_name='artwork',
            name='code',
        ),
    ]

