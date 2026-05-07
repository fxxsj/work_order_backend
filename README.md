# 印刷施工单跟踪系统 - 后端

> Django 4.2 + Django REST Framework 后端 API 服务

## 技术栈

- Python 3.12
- Django 4.2
- Django REST Framework 3.14
- PostgreSQL 16
- Redis 7

## 快速开始

### 一键启动（推荐）

```bash
./start.sh              # 交互式启动（开发环境）
./start.sh dev          # 开发环境
./start.sh prod         # 生产环境
./start.sh --skip-migrate  # 跳过迁移快速启动
```

### 手动启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 执行迁移
python manage.py migrate --skip-checks

# 3. 加载初始数据 (可选)
python manage.py load_initial_users
python manage.py loaddata workorder/fixtures/initial_products.json

# 4. 启动开发服务器
python manage.py runserver --skip-checks
```

### Docker 部署

```bash
# 启动完整服务栈 (PostgreSQL + Redis + Backend)
docker-compose up -d

# 查看日志
docker-compose logs -f backend
```

## 环境说明

| 环境 | 配置 | 用途 |
|------|------|------|
| dev | `.env` (从 `.env.example` 复制) | 本地开发 |
| prod | `.env.production` | 生产部署 |

**关键环境变量：**

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEBUG` | 调试模式 | `False` |
| `SECRET_KEY` | Django secret key | - |
| `DATABASE_URL` | PostgreSQL 连接地址 | `postgres://workorder:workorder@db:5432/workorder` |
| `REDIS_URL` | Redis 连接地址 | `redis://redis:6379/0` |
| `ALLOWED_HOSTS` | 允许的 hosts | `localhost,127.0.0.1` |

## 目录结构

```
backend/
├── config/           # Django 配置
│   ├── settings.py  # 主配置
│   ├── urls.py      # URL 路由
│   └── wsgi.py      # WSGI 配置
├── workorder/       # 主应用
│   ├── models/      # 数据模型
│   ├── views/       # API 视图
│   ├── serializers/ # 序列化器
│   ├── services/    # 业务逻辑
│   ├── policies/    # 业务规则
│   ├── signals.py   # Django 信号
│   └── tests/       # 测试
├── manage.py
├── requirements.txt
└── docker-compose.yml
```

## API 文档

启动服务后访问: http://localhost:8000/api/

## 测试

```bash
# 运行所有测试
python manage.py test

# 运行特定测试
python manage.py test workorder.tests.test_api

# 生成覆盖率报告
coverage run manage.py test
coverage report
```

## 管理命令

```bash
python manage.py migrate                      # 执行迁移
python manage.py load_initial_users         # 加载测试用户
python manage.py loaddata initial_products.json  # 加载示例产品
python manage.py init_groups               # 初始化用户组
python manage.py init_multi_level_approval # 初始化审批流
```

## 部署

### Docker (推荐)

```bash
# 开发环境快速启动
docker-compose up -d backend

# 生产构建
docker build -t workorder-backend .
docker run -p 8000:8000 workorder-backend
```

### 生产环境

```bash
pip install -r requirements.txt
python manage.py collectstatic
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

## GitHub Actions

- `ci.yml` - 测试、lint、覆盖率
- `docker.yml` - Docker 镜像构建和发布
