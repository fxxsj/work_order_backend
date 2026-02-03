#!/usr/bin/env python3
"""
简化的性能监控测试
不依赖Django，直接测试监控核心功能
(调试输出已清理)
"""

import sys
import os
import time

# 添加backend路径
sys.path.append('/home/chenjiaxing/文档/work_order/backend')

# 直接导入监控模块
from monitoring.working_monitor import (
    monitor_performance,
    metrics,
    health_monitor,
    alert_manager,
    get_performance_stats
)

@monitor_performance("test_fast_operation")
def fast_operation():
    time.sleep(0.1)
    return "Fast operation completed"

@monitor_performance("test_slow_operation") 
def slow_operation():
    time.sleep(3.0)
    return "Slow operation completed"

@monitor_performance("test_error_operation")
def error_operation():
    raise ValueError("Test error for monitoring")

def test_monitoring():
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
