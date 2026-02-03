#!/usr/bin/env python3
"""
性能监控测试脚本
用于测试监控系统的功能
(调试输出已清理)
"""

import os
import sys
import django
import time

# 设置Django环境
sys.path.append('/home/chenjiaxing/文档/work_order/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from monitoring.working_monitor import (
    monitor_performance,
    metrics,
    health_monitor,
    alert_manager,
    get_performance_stats
)

@monitor_performance("test_fast_operation")
def fast_operation():
    """快速操作测试"""
    time.sleep(0.1)
    return "Fast operation completed"

@monitor_performance("test_slow_operation")
def slow_operation():
    """慢操作测试"""
    time.sleep(3.0)
    return "Slow operation completed"

@monitor_performance("test_error_operation")
def error_operation():
    """错误操作测试"""
    raise ValueError("Test error for monitoring")

def test_monitoring():
    """测试监控功能"""
    # 测试快速操作
    result = fast_operation()
    
    # 测试慢操作
    result = slow_operation()
    
    # 测试错误操作
    try:
        error_operation()
    except ValueError:
        pass
    
    # 测试多次调用
    for i in range(5):
        fast_operation()
    
    # 生成性能报告
    report = get_performance_stats()
    
    # 返回结果供验证
    return report

if __name__ == '__main__':
    test_monitoring()
