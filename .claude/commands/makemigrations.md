---
description: 生成 Django migration 并检查
allowed-tools: Bash(python:*,cd:*)
---

# Makemigrations 命令

生成 Django 数据库迁移文件。

## 步骤

1. **生成迁移**
   ```bash
   python manage.py makemigrations --skip-checks
   ```

2. **检查生成的迁移**
   - 确认迁移文件内容正确
   - 检查是否有数据迁移需求
   - 确认无空迁移

3. **运行迁移（可选）**
   ```bash
   python manage.py migrate --skip-checks
   ```

## 注意事项

- 模型变更必须有 migration
- 不要在 migration 中写复杂业务逻辑
- 生产环境敏感操作需要数据迁移脚本
