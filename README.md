# 印刷生产管理系统 - 后端

Django 4.2 + Django REST Framework 后端 API 服务。

## 技术栈

- Python 3.12
- Django 4.2
- Django REST Framework 3.14
- PostgreSQL
- Redis / Channels / Daphne
- drf-spectacular OpenAPI 文档

## 目录结构

```
backend/
├── config/                    # Django 配置与 URL
├── monitoring/                # 监控路由
├── workorder/
│   ├── models/                # 业务模型
│   ├── serializers/           # DRF 序列化器
│   ├── views/                 # API ViewSet / View
│   ├── services/              # 业务服务层
│   ├── policies/              # 审批与权限规则
│   ├── management/commands/   # 初始化和维护命令
│   └── tests/                 # 测试
├── requirements.txt
├── manage.py
└── docker-compose.yml
```

## 快速开始

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py reset_processes --force
python manage.py init_departments
python manage.py init_groups
python manage.py load_assignment_rules
python manage.py runserver
```

默认服务地址：

- API: `http://localhost:8000/api/v1/`
- 管理后台: `http://localhost:8000/admin/`
- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`
- Health Check: `http://localhost:8000/api/health/`

## 常用命令

```bash
python manage.py migrate
python manage.py test
python -m pytest
python manage.py load_initial_users
python manage.py loaddata workorder/fixtures/initial_products.json
```

## 开发约定

- View 层只做参数校验、权限检查和响应格式化。
- 复杂业务逻辑放在 `workorder/services/`。
- 审批、状态和权限规则优先放在 `workorder/policies/` 或对应 service。
- HTTP 状态码使用 `rest_framework.status.HTTP_XXX` 常量。
- API 响应使用统一格式：`ApiResponse.success(data)` / `ApiResponse.error(message, code)`。
- 查询列表接口时使用 `select_related` / `prefetch_related` 控制 N+1。

## 文档

- 根文档索引：[../docs/README.md](../docs/README.md)
- API 参考：[../docs/BACKEND_API.md](../docs/BACKEND_API.md)
- 施工单流程服务：[../docs/WORKORDER_FLOW_SERVICE.md](../docs/WORKORDER_FLOW_SERVICE.md)
- 字段说明：[../docs/WORKORDER_FIELDS.md](../docs/WORKORDER_FIELDS.md)
