# 印刷施工单跟踪系统 API 文档

## 概述

本系统提供 RESTful API 用于施工单和任务管理。API 文档使用 OpenAPI 3.0 规范编写。

## 在线文档

开发环境启动后，可访问以下地址查看交互式 API 文档：

- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/
- **OpenAPI Schema**: http://localhost:8000/api/schema/

## Schema 文件

- `openapi.yaml` - OpenAPI 3.0 规范（YAML 格式）
- `openapi.json` - OpenAPI 3.0 规范（JSON 格式）

## 认证方式

API 使用 Token 认证。在请求头中包含：

```
Authorization: Token your_token_here
```

获取 Token：
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "your_username", "password": "your_password"}'
```

响应：
```json
{
  "token": "your_auth_token",
  "user_id": 1,
  "username": "your_username"
}
```

## API 端点分类

### 施工单 (WorkOrders)
- `GET /api/workorders/` - 获取施工单列表
- `POST /api/workorders/` - 创建施工单
- `GET /api/workorders/{id}/` - 获取施工单详情
- `PUT /api/workorders/{id}/` - 更新施工单
- `DELETE /api/workorders/{id}/` - 删除施工单
- `POST /api/workorders/{id}/approve/` - 审核通过
- `POST /api/workorders/{id}/reject/` - 审核拒绝

### 任务 (Tasks)
- `GET /api/workorder-tasks/` - 获取任务列表
- `GET /api/workorder-tasks/{id}/` - 获取任务详情
- `POST /api/workorder-tasks/{id}/assign/` - 分配任务
- `POST /api/workorder-tasks/{id}/claim/` - 认领任务
- `POST /api/workorder-tasks/{id}/start/` - 开始任务
- `POST /api/workorder-tasks/{id}/complete/` - 完成任务
- `POST /api/workorder-tasks/{id}/cancel/` - 取消任务
- `POST /api/workorder-tasks/bulk-assign/` - 批量分配
- `POST /api/workorder-tasks/bulk-delete/` - 批量删除

### 通知 (Notifications)
- `GET /api/notifications/` - 获取通知列表
- `POST /api/notifications/{id}/mark_read/` - 标记已读
- `POST /api/notifications/mark_all_read/` - 全部标记已读
- `GET /api/notifications/unread_count/` - 未读数量

### 统计 (Statistics)
- `GET /api/workorder-tasks/department_workload/` - 部门工作负载
- `GET /api/workorder-tasks/collaboration_stats/` - 协作统计
- `GET /api/workorder-tasks/operator_center/` - 操作员中心

### 系统配置
- `GET /api/departments/` - 部门列表
- `GET /api/processes/` - 工序列表
- `GET /api/task-assignment-rules/` - 任务分派规则
- `POST /api/task-assignment-rules/` - 创建分派规则

## 请求/响应格式

### 分页响应
列表接口返回分页数据：
```json
{
  "count": 100,
  "next": "http://api.example.com/api/tasks/?page=2",
  "previous": null,
  "results": [...]
}
```

### 错误响应
```json
{
  "error": "错误类型",
  "message": "详细错误信息",
  "details": {}
}
```

## 使用示例

### 创建施工单
```bash
curl -X POST http://localhost:8000/api/workorders/ \
  -H "Authorization: Token your_token" \
  -H "Content-Type: application/json" \
  -d '{
    "customer": 1,
    "production_quantity": 1000,
    "delivery_date": "2026-12-31",
    "priority": "normal",
    "processes": [
      {"process": 1, "sequence": 10},
      {"process": 2, "sequence": 20}
    ]
  }'
```

### 分配任务
```bash
curl -X POST http://localhost:8000/api/workorder-tasks/123/assign/ \
  -H "Authorization: Token your_token" \
  -H "Content-Type: application/json" \
  -d '{"operator_id": 45, "notes": "紧急任务"}'
```

### 查询任务
```bash
curl -X GET "http://localhost:8000/api/workorder-tasks/?status=pending&assigned_department=1" \
  -H "Authorization: Token your_token"
```

### 更新任务进度
```bash
curl -X POST http://localhost:8000/api/workorder-tasks/123/update_quantity/ \
  -H "Authorization: Token your_token" \
  -H "Content-Type: application/json" \
  -d '{
    "quantity_increment": 100,
    "quantity_defective": 5,
    "notes": "今日完成"
  }'
```

## 客户端 SDK 生成

使用 OpenAPI schema 可以生成各种语言的客户端 SDK：

```bash
# 使用 openapi-generator
openapi-generator-cli generate -i openapi.yaml -g javascript -o ./client-js
openapi-generator-cli generate -i openapi.yaml -g python -o ./client-python
openapi-generator-cli generate -i openapi.yaml -g typescript-axios -o ./client-ts
```

## 版本历史

- **v1.0.0** (2026-02-02) - 初始版本，包含核心任务管理功能

## 技术支持

如需技术支持，请查看：
- 系统文档: `/docs/`
- 用户手册: `/docs/USER_MANUAL.md`
- 部署指南: `/docs/DEPLOYMENT.md`
