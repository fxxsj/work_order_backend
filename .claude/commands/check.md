---
description: 运行后端代码检查，包括 Django check 和 lint
allowed-tools: Bash(python:*,cd:*)
---

# Check 命令

运行后端代码检查工具。

## 步骤

1. **Django 系统检查**
   ```bash
   bash scripts/check.sh
   ```

2. **问题分析**
   - 列出 Django check 警告/错误
   - 列出 flake8 发现的问题
   - 提供修复建议

## 输出格式

```markdown
## 代码检查报告

### Django Check
- ✅ 通过 / ⚠️ N warnings / ❌ N errors

### Lint (flake8)
- ✅ 通过 / ❌ N issues

### 发现的问题
- 列出需要修复的问题
```
