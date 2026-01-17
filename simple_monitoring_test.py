#!/usr/bin/env python3
"""
简化的性能监控测试
不依赖Django，直接测试监控核心功能
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
    print("🧪 Testing Performance Monitoring System")
    print("=" * 50)
    
    # 测试快速操作
    print("1. Testing fast operation...")
    result = fast_operation()
    print(f"   Result: {result}")
    
    # 测试慢操作
    print("\n2. Testing slow operation...")
    result = slow_operation()
    print(f"   Result: {result}")
    
    # 测试错误操作
    print("\n3. Testing error operation...")
    try:
        error_operation()
    except ValueError as e:
        print(f"   Expected error caught: {e}")
    
    # 测试多次调用
    print("\n4. Testing multiple operations...")
    for i in range(5):
        fast_operation()
    
    # 生成性能报告
    print("\n5. Generating performance report...")
    report = get_performance_stats()
    
    print("\n📊 Performance Metrics:")
    for name, stats in report['metrics'].items():
        if stats and stats.get('count', 0) > 0:
            print(f"  {name}:")
            print(f"    Count: {stats['count']}")
            print(f"    Avg: {stats['avg']:.3f}s")
            print(f"    Min: {stats['min']:.3f}s") 
            print(f"    Max: {stats['max']:.3f}s")
    
    print("\n🖥️  System Health:")
    health = report['health']
    print(f"  Uptime: {health['uptime']:.1f}s")
    print(f"  Database Status: {health['database']['status']}")
    
    print("\n🚨 Alerts:")
    alerts = report['alerts']
    if alerts:
        for alert in alerts:
            print(f"  {alert['severity'].upper()}: {alert['message']}")
    else:
        print("  No active alerts")
    
    print("\n✅ Monitoring system test completed!")

if __name__ == '__main__':
    test_monitoring()