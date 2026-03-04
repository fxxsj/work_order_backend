#!/bin/bash
# 审计日志系统集成脚本
# Author: 小可 AI Assistant
# Date: 2026-03-04

set -e

echo "================================"
echo "  审计日志系统集成工具"
echo "================================"
echo ""

# 检查是否在 backend 目录
if [ ! -f "manage.py" ]; then
    echo "❌ 错误: 请在 backend 目录下运行此脚本"
    exit 1
fi

# 激活虚拟环境
echo "📦 激活虚拟环境..."
source venv/bin/activate

echo ""
echo "🔧 步骤 1/7: 更新模型导入..."
python << 'EOF'
import sys
sys.path.insert(0, '.')

# 更新 models/__init__.py
init_file = 'workorder/models/__init__.py'

# 检查是否已导入
with open(init_file, 'r', encoding='utf-8') as f:
    content = f.read()

if 'AuditLog' not in content:
    # 添加导入
    import_section = """from .audit import (
    AuditLog,
    AuditLogExport,
    AuditLogSettings,
)"""

    with open(init_file, 'a', encoding='utf-8') as f:
        f.write('\n' + import_section)

    print("✅ 已更新 models/__init__.py")
else:
    print("✅ models/__init__.py 已包含 AuditLog 导入")
EOF

echo ""
echo "🔧 步骤 2/7: 注册中间件..."
python << 'EOF'
import sys
sys.path.insert(0, '.')

settings_file = 'config/settings.py'

with open(settings_file, 'r', encoding='utf-8') as f:
    content = f.read()

if 'AuditLogMiddleware' not in content:
    # 找到 MIDDLEWARE 列表
    if 'MIDDLEWARE = [' in content:
        # 在第一个 middleware 之前插入
        new_line = "    'workorder.middleware.audit_log.AuditLogMiddleware',\n"
        content = content.replace(
            "MIDDLEWARE = [",
            f"MIDDLEWARE = [\n{new_line}"
        )

        with open(settings_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print("✅ 已注册 AuditLogMiddleware")
    else:
        print("⚠️  未找到 MIDDLEWARE 配置")
else:
    print("✅ AuditLogMiddleware 已注册")
EOF

echo ""
echo "🔧 步骤 3/7: 注册视图路由..."
python << 'EOF'
import sys
sys.path.insert(0, '.')

urls_file = 'workorder/urls.py'

with open(urls_file, 'r', encoding='utf-8') as f:
    content = f.read()

if 'AuditLogViewSet' not in content:
    # 添加导入
    import_line = "from .views.audit_log import AuditLogViewSet\n"

    # 找到 router.register
    if 'router.register' in content:
        content = content.replace(
            "router.register(r'workorders-flow',",
            f"{import_line}\nrouter.register(r'audit-logs', AuditLogViewSet, basename='audit-log')\nrouter.register(r'workorders-flow',"
        )

        with open(urls_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print("✅ 已注册 AuditLogViewSet 路由")
    else:
        print("⚠️  未找到 router 配置")
else:
    print("✅ AuditLogViewSet 路由已注册")
EOF

echo ""
echo "🔧 步骤 4/7: 注册应用信号..."
python << 'EOF'
import sys
import os
sys.path.insert(0, '.')

# 创建 signals.py 文件
signals_file = 'workorder/signals.py'

if not os.path.exists(signals_file):
    with open(signals_file, 'w', encoding='utf-8') as f:
        f.write('''"""
审计日志信号注册

Author: 小可 AI Assistant
Date: 2026-03-04
"""

from django.apps import apps
from workorder.services.audit_log_service import register_audit_signals

def register_audit_signals():
    """
    注册所有需要审计的模型的信号
    """
    for app_config in apps.get_app_configs():
        if app_config.name == 'workorder':
            register_audit_signals(app_config)
            break

# 在应用启动时注册
from django.apps import AppConfig

class WorkorderConfig(AppConfig):
    def ready(self):
        import workorder.signals  # noqa
''')
    print("✅ 已创建 signals.py")
else:
    print("✅ signals.py 已存在")
EOF

echo ""
echo "🔧 步骤 5/7: 创建数据库迁移..."
python manage.py makemigrations workorder --name add_audit_log_models || echo "⚠️  makemigrations 失败（可能已存在）"

echo ""
echo "🔧 步骤 6/7: 执行数据库迁移..."
python manage.py migrate || echo "❌ migrate 失败"

echo ""
echo "🔧 步骤 7/7: 创建默认配置..."
python << 'EOF'
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from workorder.models.audit import AuditLogSettings

# 创建或更新默认配置
settings, created = AuditLogSettings.objects.get_or_create(
    pk=1,
    defaults={
        'retention_days': 365,
        'enabled': True,
        'audited_models': [
            'workorder.WorkOrder',
            'workorder.WorkOrderTask',
            'workorder.WorkOrderProcess',
            'workorder.Customer',
            'workorder.Product',
            'workorder.Material',
            'auth.User',
        ],
        'excluded_fields': ['last_login', 'updated_at'],
    }
)

if created:
    print("✅ 已创建审计日志默认配置")
else:
    print("✅ 审计日志配置已存在")
EOF

echo ""
echo "================================"
echo "  ✅ 集成完成！"
echo "================================"
echo ""
echo "📋 后续步骤："
echo ""
echo "1. 为需要审计的模型添加 AuditMixin:"
echo "   class WorkOrder(AuditMixin, models.Model):"
echo "       # ..."
echo ""
echo "2. 重启服务器:"
echo "   python manage.py runserver"
echo ""
echo "3. 测试审计日志:"
echo "   python manage.py audit_log --stats"
echo ""
echo "4. 查看 API 文档:"
echo "   http://localhost:8000/api/v1/docs/"
echo ""
echo "📚 详细文档: docs/AUDIT_LOG_IMPLEMENTATION.md"
echo ""
