# Generated manually on 2026-01-XX

from django.db import migrations, models
import django.db.models.deletion


def migrate_department_data(apps, schema_editor):
    """将原有的department数据迁移到departments多对多字段"""
    UserProfile = apps.get_model('workorder', 'UserProfile')
    Department = apps.get_model('workorder', 'Department')
    
    # 遍历所有UserProfile，将department添加到departments
    for profile in UserProfile.objects.all().select_related('department'):
        # 在迁移时，旧的department字段仍然存在
        old_department_id = getattr(profile, 'department_id', None)
        if old_department_id:
            try:
                department = Department.objects.get(id=old_department_id)
                # 使用through表直接添加关系（因为此时departments字段已存在）
                profile.departments.add(department)
            except Department.DoesNotExist:
                pass


def reverse_migrate_department_data(apps, schema_editor):
    """回滚：将departments的第一个部门设置回department字段"""
    UserProfile = apps.get_model('workorder', 'UserProfile')
    
    # 在回滚时，执行顺序是：
    # 1. RemoveField反向 -> 重新添加department字段
    # 2. 执行这个函数 -> 此时departments还存在，department字段刚被添加
    # 3. AddField反向 -> 删除departments字段
    for profile in UserProfile.objects.all().prefetch_related('departments'):
        if profile.departments.exists():
            # 取第一个部门作为department
            first_dept = profile.departments.first()
            if first_dept:
                profile.department_id = first_dept.id
                profile.save()


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0067_update_department_hierarchy'),
    ]

    operations = [
        # 1. 先添加新的departments字段（ManyToManyField）
        migrations.AddField(
            model_name='userprofile',
            name='departments',
            field=models.ManyToManyField(
                blank=True,
                help_text='用户所属的部门（可多选）',
                to='workorder.department',
                verbose_name='所属部门'
            ),
        ),
        # 2. 迁移数据：将原有的department数据复制到departments
        migrations.RunPython(migrate_department_data, reverse_migrate_department_data),
        # 3. 删除旧的department字段（ForeignKey）
        migrations.RemoveField(
            model_name='userprofile',
            name='department',
        ),
    ]

