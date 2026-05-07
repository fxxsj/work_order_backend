# 印刷施工单跟踪系统 - 后端

> Django 4.2 + DRF 后端 API 服务

## 技术栈

- Python 3.12, Django 4.2, DRF 3.14, PostgreSQL, Redis

## 关键文件

- `config/settings.py` - Django 配置
- `workorder/models/` - 数据模型 (模块化)
- `workorder/views/` - API 视图
- `workorder/serializers/` - DRF 序列化器
- `workorder/services/` - 业务逻辑层
- `workorder/policies/` - 审批规则

## 架构模式

- **Views** - 薄层，只做参数验证和响应格式化
- **Services** - 业务逻辑 (work_order_service, task_assignment 等)
- **Policies** - 审批规则和权限
- 统一异常: `ServiceError(message, code=status.HTTP_XXX)`
- 统一响应: `ApiResponse.success(data)` / `ApiResponse.error(message, code)`

## Critical Rules

- HTTP status code 必须用 `status.HTTP_XXX` 常量
- 新功能走 Service Layer，禁止在 Views 里写复杂业务逻辑
- 模型变更必须有 migration
- 查询优化: `select_related` / `prefetch_related` 避免 N+1

## 开发命令

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
python manage.py test
```

## Skill Activation

- Django API → `django-api-patterns` + `django-patterns`
- 数据库迁移 → `database-migrations`
- 写测试 → `django-tdd`
