#!/usr/bin/env python3
"""
审计日志系统问题修复脚本

Author: 小可 AI Assistant
Date: 2026-03-04
"""

import os
import sys

def fix_export_service_call():
    """修复1：导出服务方法调用"""
    file_path = 'workorder/views/audit_log.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'export_service.trigger_export(export)' in content:
        content = content.replace(
            'export_service.trigger_export(export)',
            'export_service.perform_export(str(export.id))'
        )

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print("✅ 已修复导出服务调用")
        return True
    else:
        print("✅ 导出服务调用已是正确版本")
        return True

def fix_missing_imports():
    """修复2：添加缺失的导入"""
    file_path = 'workorder/services/audit_log_service.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否已导入
    if 'from django.contrib.contenttypes.models import ContentType' not in content:
        # 在导入部分添加
        import_section = '''from django.contrib.contenttypes.models import ContentType
'''

        # 找到 from django.db.models 导入行之后插入
        content = content.replace(
            'from django.db.models import',
            f'{import_section}from django.db.models import'
        )

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print("✅ 已添加 ContentType 导入")
        return True
    else:
        print("✅ ContentType 导入已存在")
        return True

def fix_base_class():
    """修复3：检查基类"""
    file_path = 'workorder/views/base_viewsets.py'

    if not os.path.exists(file_path):
        print("⚠️  base_viewsets.py 不存在，将在 audit_log.py 中使用标准基类")
        # 在 audit_log.py 中使用标准基类
        audit_log_path = 'workorder/views/audit_log.py'

        with open(audit_log_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 替换导入
        content = content.replace(
            'from .base_viewsets import ReadOnlyBaseViewSet',
            '''from rest_framework import viewsets as drf_viewsets

class ReadOnlyBaseViewSet(drf_viewsets.ReadOnlyModelViewSet):
    """只读视图集基类"""
    pass
'''
        )

        with open(audit_log_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print("✅ 已在 audit_log.py 中定义标准基类")
        return True

    # 检查是否定义了 ReadOnlyBaseViewSet
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'class ReadOnlyBaseViewSet' in content:
        print("✅ ReadOnlyBaseViewSet 已定义")
        return True
    else:
        print("⚠️  base_viewsets.py 中未定义 ReadOnlyBaseViewSet")
        print("   建议手动添加或使用标准 DRF 基类")
        return False

def verify_fixes():
    """验证修复结果"""
    print("\n🔍 验证修复...")

    # 检查语法
    import subprocess

    files_to_check = [
        'workorder/models/audit.py',
        'workorder/services/audit_log_service.py',
        'workorder/services/audit_export_service.py',
        'workorder/middleware/audit_log.py',
        'workorder/views/audit_log.py',
        'workorder/serializers/audit.py',
    ]

    all_ok = True
    for file_path in files_to_check:
        result = subprocess.run(
            ['python', '-m', 'py_compile', file_path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"✅ {file_path} 语法正确")
        else:
            print(f"❌ {file_path} 有语法错误:")
            print(result.stderr)
            all_ok = False

    return all_ok

def main():
    """主函数"""
    print("=" * 50)
    print("  审计日志系统问题修复脚本")
    print("=" * 50)
    print()

    # 检查目录
    if not os.path.exists('manage.py'):
        print("❌ 错误: 请在 backend 目录下运行此脚本")
        sys.exit(1)

    # 切换到虚拟环境
    venv_python = 'venv/bin/python'
    if not os.path.exists(venv_python):
        print("❌ 虚拟环境不存在")
        sys.exit(1)

    print("🔧 开始修复...\n")

    # 执行修复
    results = []
    results.append(fix_export_service_call())
    results.append(fix_missing_imports())
    results.append(fix_base_class())

    print()
    print("=" * 50)

    if all(results):
        print("✅ 所有修复已完成")
        print()

        # 验证
        if verify_fixes():
            print()
            print("=" * 50)
            print("  ✅ 修复成功！代码已准备就绪")
            print("=" * 50)
            print()
            print("📋 下一步:")
            print("1. 创建数据库迁移:")
            print("   python manage.py makemigrations")
            print("   python manage.py migrate")
            print()
            print("2. 运行集成脚本:")
            print("   ./setup_audit_log.sh")
            print()
            print("3. 重启服务器测试")
            sys.exit(0)
        else:
            print()
            print("⚠️  验证失败，请检查错误信息")
            sys.exit(1)
    else:
        print("❌ 部分修复失败，请手动检查")
        sys.exit(1)

if __name__ == '__main__':
    main()
