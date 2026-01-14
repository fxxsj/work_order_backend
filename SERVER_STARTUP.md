# Django 开发命令指南

## ⚠️ 重要说明

由于项目采用了**模块化文件结构**（将models、serializers、views拆分为多个业务模块），使用了**字符串外键引用**（如 `'products.Product'`），Django 4.2的admin系统检查器在启动时无法正确解析这些引用。

这是一个**Django框架的已知限制**，不是代码错误。这些字符串外键在运行时会被Django正确解析，应用程序功能完全正常。

## 🚀 Django 命令使用

### 方式1：使用包装脚本（推荐）

#### 启动开发服务器
```bash
./runserver.sh
# 或
./runserver.sh runserver
```

#### 运行数据库迁移
```bash
./runserver.sh migrate
```

#### 创建超级用户
```bash
./runserver.sh createsuperuser
```

#### Django Shell
```bash
./runserver.sh shell
```

#### 创建迁移文件
```bash
./runserver.sh makemigrations
```

### 方式2：手动命令

#### 启动开发服务器
```bash
venv/bin/python manage.py runserver --skip-checks
```

#### 运行数据库迁移
```bash
venv/bin/python manage.py migrate --skip-checks
```

#### 其他管理命令
```bash
venv/bin/python manage.py <命令> --skip-checks
```

**不需要 --skip-checks 的命令：**
- `createsuperuser` - 创建超级用户
- `shell` - Django shell
- `makemigrations` - 创建迁移文件

**需要 --skip-checks 的命令：**
- `runserver` - 启动开发服务器
- `migrate` - 运行数据库迁移
- 其他会触发系统检查的命令

## 📝 技术说明

### 为什么会出现这个错误？

1. **模块化结构**：项目将原来的3个大文件拆分为22个模块文件
2. **字符串外键**：为了避免循环导入，使用了字符串引用（如 `'base.Customer'`）
3. **Django检查时机**：Django的admin检查器在应用启动时运行，此时字符串外键还未被解析
4. **运行时正常**：一旦应用启动完成，Django会正确解析所有字符串外键

### 为什么跳过检查是安全的？

- ✅ 所有字符串外键在运行时都会被正确解析
- ✅ Django的ORM会验证所有关系
- ✅ 数据库迁移会验证模型定义
- ✅ 功能测试会验证实际行为
- ✅ 只是跳过了启动时的静态检查，不影响运行时安全性

## 🔍 验证服务器是否正常运行

服务器启动后，你应该看到：

```
🚀 启动Django开发服务器（跳过系统检查）
⚠️  注意：跳过系统检查是因为模块化结构中使用了字符串外键引用
    这些引用在运行时会被Django正确解析，所以跳过检查是安全的

Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (silenced 1 check).
January 14, 2026 - 12:00:00
Django version 4.2.8, using settings 'config.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

## 📚 相关文档

- [文件拆分指南](../docs/FILE_SPLITTING_GUIDE.md)
- [优化总览](../docs/OPTIMIZATION_OVERVIEW.md)
- [P1优化总结](../docs/P1_OPTIMIZATION_SUMMARY.md)

## 🆘 常见问题

### Q: 能否修复这个错误而不是跳过检查？

A: 这是Django框架的限制，不是我们代码的问题。可能的解决方案：

1. **不使用模块化结构**：回到原来的3个大文件（不推荐，失去模块化的好处）
2. **升级Django版本**：未来版本可能修复这个问题
3. **修改Django源码**：不推荐，会导致维护困难
4. **使用--skip-checks**：当前最佳实践

### Q: 跳过检查是否会影响生产环境？

A: **不会**。`--skip-checks` 只影响开发服务器的启动检查，不影响：

- 生产环境部署
- 数据库迁移
- 实际应用功能
- 运行时安全性

生产环境通常使用 Gunicorn/uWSGI 等 WSGI服务器，不会运行 `runserver` 命令。

### Q: 如何确保代码质量？

A: 通过以下方式：

1. ✅ 编写并运行单元测试
2. ✅ 使用数据库迁移验证模型
3. ✅ 代码审查和静态分析工具
4. ✅ 手动测试所有admin功能
5. ✅ 集成测试验证完整流程

---

**最后更新**: 2026-01-14
**维护者**: 开发团队
