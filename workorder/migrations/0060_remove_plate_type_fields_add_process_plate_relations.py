# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0059_add_foiling_embossing_plate_type_to_workorder'),
    ]

    operations = [
        # 在 Process 模型中添加工序与版的关系配置字段
        migrations.AddField(
            model_name='process',
            name='requires_artwork',
            field=models.BooleanField(default=False, help_text='该工序是否需要图稿（CTP版）', verbose_name='需要图稿'),
        ),
        migrations.AddField(
            model_name='process',
            name='requires_die',
            field=models.BooleanField(default=False, help_text='该工序是否需要刀模', verbose_name='需要刀模'),
        ),
        migrations.AddField(
            model_name='process',
            name='requires_foiling_plate',
            field=models.BooleanField(default=False, help_text='该工序是否需要烫金版', verbose_name='需要烫金版'),
        ),
        migrations.AddField(
            model_name='process',
            name='requires_embossing_plate',
            field=models.BooleanField(default=False, help_text='该工序是否需要压凸版', verbose_name='需要压凸版'),
        ),
        migrations.AddField(
            model_name='process',
            name='artwork_required',
            field=models.BooleanField(default=True, help_text='如果为True，选择该工序时必须选择图稿；如果为False，图稿可选（未选择时生成设计任务）', verbose_name='图稿必选'),
        ),
        migrations.AddField(
            model_name='process',
            name='die_required',
            field=models.BooleanField(default=True, help_text='如果为True，选择该工序时必须选择刀模；如果为False，刀模可选（未选择时生成设计任务）', verbose_name='刀模必选'),
        ),
        migrations.AddField(
            model_name='process',
            name='foiling_plate_required',
            field=models.BooleanField(default=True, help_text='如果为True，选择该工序时必须选择烫金版；如果为False，烫金版可选（未选择时生成设计任务）', verbose_name='烫金版必选'),
        ),
        migrations.AddField(
            model_name='process',
            name='embossing_plate_required',
            field=models.BooleanField(default=True, help_text='如果为True，选择该工序时必须选择压凸版；如果为False，压凸版可选（未选择时生成设计任务）', verbose_name='压凸版必选'),
        ),
        # 从 WorkOrder 模型中移除类型字段
        migrations.RemoveField(
            model_name='workorder',
            name='artwork_type',
        ),
        migrations.RemoveField(
            model_name='workorder',
            name='die_type',
        ),
        migrations.RemoveField(
            model_name='workorder',
            name='foiling_plate_type',
        ),
        migrations.RemoveField(
            model_name='workorder',
            name='embossing_plate_type',
        ),
    ]

