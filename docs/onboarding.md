# 后端上手指南

## 前置要求

- Python 3.12+
- PostgreSQL 16（或 Docker）
- Redis 7（可选）

## 快速开始

```bash
# 安装
bash scripts/setup.sh

# 启动开发服务器
bash scripts/dev-up.sh

# 运行测试
bash scripts/test.sh

# 运行检查
bash scripts/check.sh
```

## 手动安装（如脚本不可用）

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --skip-checks
python manage.py runserver --skip-checks
```

## 开发命令

```bash
source venv/bin/activate

# 运行服务器
python manage.py runserver --skip-checks

# 生成迁移
python manage.py makemigrations --skip-checks

# 运行迁移
python manage.py migrate --skip-checks

# 运行测试
python manage.py test workorder.tests --verbosity=2

# Django shell
python manage.py shell --skip-checks

# 创建超级用户
python manage.py createsuperuser
```

## 注意事项

- `--skip-checks` 是因为模块化结构使用了字符串外键引用，运行时会被正确解析
- 模型变更必须有 migration
- 新增 API 请同时更新 `BACKEND_API.md`
