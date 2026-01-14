# 生成数据库索引的迁移文件
# python manage.py makemigrations workorder --empty

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('workorder', '0001_initial'),  # 替换为最新的迁移文件
    ]

    operations = [
        # WorkOrder 索引
        migrations.AddIndex(
            model_name='workorder',
            index=models.Index(fields=['order_number'], name='wo_order_number_idx'),
        ),
        migrations.AddIndex(
            model_name='workorder',
            index=models.Index(fields=['customer'], name='wo_customer_idx'),
        ),
        migrations.AddIndex(
            model_name='workorder',
            index=models.Index(fields=['status'], name='wo_status_idx'),
        ),
        migrations.AddIndex(
            model_name='workorder',
            index=models.Index(fields=['created_at'], name='wo_created_at_idx'),
        ),
        migrations.AddIndex(
            model_name='workorder',
            index=models.Index(fields=['-created_at'], name='wo_created_at_desc_idx'),
        ),

        # WorkOrderTask 索引
        migrations.AddIndex(
            model_name='workordertask',
            index=models.Index(fields=['work_order_process'], name='task_process_idx'),
        ),
        migrations.AddIndex(
            model_name='workordertask',
            index=models.Index(fields=['status'], name='task_status_idx'),
        ),
        migrations.AddIndex(
            model_name='workordertask',
            index=models.Index(fields=['assigned_operator'], name='task_operator_idx'),
        ),
        migrations.AddIndex(
            model_name='workordertask',
            index=models.Index(fields=['assigned_department'], name='task_dept_idx'),
        ),

        # Product 索引
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['name'], name='product_name_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['code'], name='product_code_idx'),
        ),

        # Material 索引
        migrations.AddIndex(
            model_name='material',
            index=models.Index(fields=['name'], name='material_name_idx'),
        ),
        migrations.AddIndex(
            model_name='material',
            index=models.Index(fields=['code'], name='material_code_idx'),
        ),

        # Customer 索引
        migrations.AddIndex(
            model_name='customer',
            index=models.Index(fields=['name'], name='customer_name_idx'),
        ),
        migrations.AddIndex(
            model_name='customer',
            index=models.Index(fields=['salesperson'], name='customer_salesperson_idx'),
        ),

        # Artwork 索引
        migrations.AddIndex(
            model_name='artwork',
            index=models.Index(fields=['base_code'], name='artwork_base_code_idx'),
        ),
        migrations.AddIndex(
            model_name='artwork',
            index=models.Index(fields=['version'], name='artwork_version_idx'),
        ),

        # ProcessLog 索引
        migrations.AddIndex(
            model_name='processlog',
            index=models.Index(fields=['work_order'], name='processlog_wo_idx'),
        ),
        migrations.AddIndex(
            model_name='processlog',
            index=models.Index(fields=['created_at'], name='processlog_created_at_idx'),
        ),

        # TaskLog 索引
        migrations.AddIndex(
            model_name='tasklog',
            index=models.Index(fields=['task'], name='tasklog_task_idx'),
        ),
        migrations.AddIndex(
            model_name='tasklog',
            index=models.Index(fields=['created_at'], name='tasklog_created_at_idx'),
        ),
    ]
