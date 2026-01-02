# Generated manually for task management system

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workorder', '0041_add_version_to_artwork'),
    ]

    operations = [
        # 1. 添加 Process.task_generation_rule 字段
        migrations.AddField(
            model_name='process',
            name='task_generation_rule',
            field=models.CharField(
                choices=[
                    ('artwork', '按图稿生成任务（每个图稿一个任务，数量为1）'),
                    ('die', '按刀模生成任务（每个刀模一个任务，数量为1）'),
                    ('product', '按产品生成任务（每个产品一个任务）'),
                    ('material', '按物料生成任务（每个物料一个任务）'),
                    ('general', '生成通用任务（一个工序一个任务）'),
                ],
                default='general',
                help_text='该工序如何生成任务',
                max_length=20,
                verbose_name='任务生成规则'
            ),
        ),
        # 2. 添加 Material.need_cutting 字段
        migrations.AddField(
            model_name='material',
            name='need_cutting',
            field=models.BooleanField(
                default=False,
                help_text='该物料是否需要开料工序处理',
                verbose_name='需要开料'
            ),
        ),
        # 3. 添加 Artwork 确认相关字段
        migrations.AddField(
            model_name='artwork',
            name='confirmed',
            field=models.BooleanField(
                default=False,
                help_text='设计部是否已确认该图稿',
                verbose_name='已确认'
            ),
        ),
        migrations.AddField(
            model_name='artwork',
            name='confirmed_at',
            field=models.DateTimeField(
                blank=True,
                help_text='设计部是否已确认该图稿',
                null=True,
                verbose_name='确认时间'
            ),
        ),
        migrations.AddField(
            model_name='artwork',
            name='confirmed_by',
            field=models.ForeignKey(
                blank=True,
                help_text='设计部是否已确认该图稿',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='confirmed_artworks',
                to=settings.AUTH_USER_MODEL,
                verbose_name='确认人'
            ),
        ),
        # 4. 扩展 WorkOrderTask 模型
        migrations.AddField(
            model_name='workordertask',
            name='task_type',
            field=models.CharField(
                choices=[
                    ('artwork', '图稿任务'),
                    ('die', '刀模任务'),
                    ('product', '产品任务'),
                    ('material', '物料任务'),
                    ('general', '通用任务'),
                ],
                default='general',
                help_text='任务类型，用于区分不同的任务生成规则',
                max_length=20,
                verbose_name='任务类型'
            ),
        ),
        migrations.AddField(
            model_name='workordertask',
            name='artwork',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tasks',
                to='workorder.artwork',
                verbose_name='关联图稿'
            ),
        ),
        migrations.AddField(
            model_name='workordertask',
            name='die',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tasks',
                to='workorder.die',
                verbose_name='关联刀模'
            ),
        ),
        migrations.AddField(
            model_name='workordertask',
            name='product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tasks',
                to='workorder.product',
                verbose_name='关联产品'
            ),
        ),
        migrations.AddField(
            model_name='workordertask',
            name='material',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tasks',
                to='workorder.material',
                verbose_name='关联物料'
            ),
        ),
        migrations.AddField(
            model_name='workordertask',
            name='quantity_completed',
            field=models.IntegerField(
                default=0,
                help_text='任务完成数量，可自动计算或手动输入',
                verbose_name='完成数量'
            ),
        ),
        migrations.AddField(
            model_name='workordertask',
            name='auto_calculate_quantity',
            field=models.BooleanField(
                default=True,
                help_text='是否自动计算完成数量',
                verbose_name='自动计算数量'
            ),
        ),
        # 5. 创建 UserProfile 模型
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('department', models.ForeignKey(
                    blank=True,
                    help_text='用户所属的部门',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='workorder.department',
                    verbose_name='所属部门'
                )),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='profile',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='用户'
                )),
            ],
            options={
                'verbose_name': '用户扩展信息',
                'verbose_name_plural': '用户扩展信息管理',
            },
        ),
    ]

