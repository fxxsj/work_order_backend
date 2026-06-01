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

## Removed Compatibility

- 施工单审批统一使用 `/api/v1/workorders-flow/`，不要在 `workorders` ViewSet 新增审批动作。
- 任务分派请求字段统一使用 `assigned_operator`，不要恢复 `operator_id` 请求别名。
- 施工单筛选 `approval_status=pending` 不再映射为 `submitted`；待审核状态直接传 `submitted`。
- 对账单列表筛选类型参数统一使用 `type`，客户过滤使用 `customer`，不要恢复 `statement_type` / `partner` 查询别名。
- 对账单响应字段使用 `start_date`、`end_date`、`total_debit`、`total_credit`，不要恢复 `period_start`、`period_end`、`debit_amount`、`credit_amount` 响应别名。
- 任务日志增量使用 `quantity_increment`，不要再从 `quantity_before` / `quantity_after` 计算旧数据 fallback。
- 任务工序编码通过 `work_order_process.process.code` 获取，不要恢复 `WorkOrderTask.process_code` 兼容 property。

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
