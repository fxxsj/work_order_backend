# 后端架构

> Django 4.2 + DRF 后端 API 服务架构说明。

## 目录结构

```
backend/
├── config/              # Django 配置
│   ├── settings.py      # 主配置
│   └── urls.py          # 根路由
├── workorder/           # 主业务应用
│   ├── models/          # 数据模型（模块化）
│   ├── views/           # API 视图（薄层）
│   ├── serializers/     # DRF 序列化器
│   ├── services/        # 业务逻辑层
│   ├── policies/        # 审批规则
│   ├── tests/           # 测试套件
│   └── docs/            # 后端文档
└── manage.py            # Django 管理命令
```

## 分层架构

```
┌─────────────────────────────────────────┐
│               API Client                │
│         (Web / Flutter / Admin)         │
└─────────────────┬───────────────────────┘
                  │ HTTP/REST
┌─────────────────▼───────────────────────┐
│               Views                     │
│  薄层：参数验证、响应格式化、权限检查      │
│  调用 → services、serializers           │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│              Services                   │
│  业务逻辑层：work_order_service、        │
│  task_assignment、approval_flow 等      │
│  抛出 → ServiceError                    │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│              Policies                   │
│  审批规则、权限校验、业务约束             │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│              Models                     │
│  Django ORM、数据持久化                 │
│  PostgreSQL / Redis                     │
└─────────────────────────────────────────┘
```

## 关键约定

- **Views 薄层**：只做参数验证和响应格式化，禁止写复杂业务逻辑
- **Services 层**：所有业务逻辑在此实现
- **Policies 层**：审批规则、权限校验
- **统一异常**：`ServiceError(message, code=status.HTTP_XXX)`
- **统一响应**：`ApiResponse.success(data)` / `ApiResponse.error(message, code)`
- **HTTP 状态码**：必须用 `status.HTTP_XXX` 常量，禁止硬编码 int
- **查询优化**：`select_related` / `prefetch_related` 避免 N+1

## API 契约

详见项目根目录 `BACKEND_API.md`。

核心端点：
- 施工单审批：`/api/v1/workorders-flow/`
- 任务分派字段：`assigned_operator`
- 待审核筛选：`approval_status=submitted`
- 对账单响应字段：`start_date`, `end_date`, `total_debit`, `total_credit`
