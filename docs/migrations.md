# 数据库迁移规范

## 生成迁移

```bash
python manage.py makemigrations --skip-checks
```

## 运行迁移

```bash
python manage.py migrate --skip-checks
```

## 迁移检查清单

- [ ] 模型变更是否必要
- [ ] 迁移文件是否包含数据迁移（如需要）
- [ ] 是否能在空数据库上运行
- [ ] 生产环境是否有零停机方案

## 回滚

```bash
# 回滚到指定迁移
python manage.py migrate workorder 000X --skip-checks

# 查看迁移历史
python manage.py showmigrations workorder
```

## 数据迁移

当需要数据转换时，使用 RunPython：

```python
from django.db import migrations

def forwards(apps, schema_editor):
    MyModel = apps.get_model('workorder', 'MyModel')
    for obj in MyModel.objects.all():
        obj.new_field = obj.old_field
        obj.save()

class Migration(migrations.Migration):
    dependencies = [...]
    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
```
