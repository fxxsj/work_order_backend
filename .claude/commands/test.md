---
description: 运行后端测试套件
allowed-tools: Bash(python:*,cd:*)
---

# Test 命令

运行后端 Django 测试套件。

## 步骤

1. **运行测试**
   ```bash
   bash scripts/test.sh
   ```

2. **失败分析**
   - 识别失败测试
   - 分析失败原因
   - 提供修复建议

## 输出格式

```markdown
## 测试报告

### 后端测试 (Django)
- ✅ 通过: X/Y
- ⏱️ 耗时: Xs

### 失败的测试
- [ ] 文件路径:行号
  - 问题: 描述
  - 建议: 修复方案
```
