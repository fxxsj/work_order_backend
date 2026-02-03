"""
性能测试脚本 - 测试 P0 优化效果
(所有调试输出已清理)
"""
import os
import sys
import django
import time

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from workorder.models import WorkOrder, WorkOrderTask, WorkOrderProcess
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

def test_workorder_list_performance():
    """测试施工单列表查询性能"""
    # 测试 1: 基础查询性能
    start = time.time()
    with CaptureQueriesContext(connection) as context:
        workorders = list(WorkOrder.objects.all()[:20])
    
    end = time.time()
    query_count = len(context.captured_queries)
    elapsed = (end - start) * 1000  # 转换为毫秒
    
    # 结果存储供后续验证
    return {
        'name': '施工单列表查询性能',
        'elapsed_ms': elapsed,
        'query_count': query_count,
        'record_count': len(workorders)
    }

def test_task_list_performance():
    """测试任务列表查询性能"""
    # 测试 1: 基础查询
    start = time.time()
    with CaptureQueriesContext(connection) as context:
        tasks = list(WorkOrderTask.objects.all()[:50])
    
    end = time.time()
    query_count = len(context.captured_queries)
    elapsed = (end - start) * 1000
    
    # 结果存储供后续验证
    return {
        'name': '任务列表查询性能',
        'elapsed_ms': elapsed,
        'query_count': query_count,
        'record_count': len(tasks)
    }

def test_index_usage():
    """测试索引使用情况"""
    cursor = connection.cursor()
    
    # 检查 WorkOrder 索引
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND tbl_name='workorder_workorder' 
        AND name LIKE 'workorder_w_%'
        ORDER BY name
    """)
    indexes = cursor.fetchall()
    
    # 检查 WorkOrderTask 索引
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND tbl_name='workorder_workordertask' 
        AND name LIKE 'workorder_w_%'
        ORDER BY name
    """)
    task_indexes = cursor.fetchall()
    
    # 检查 WorkOrderProcess 索引
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND tbl_name='workorder_workorderprocess' 
        AND name LIKE 'workorder_w_%'
        ORDER BY name
    """)
    process_indexes = cursor.fetchall()
    
    return {
        'workorder_indexes': len(indexes),
        'task_indexes': len(task_indexes),
        'process_indexes': len(process_indexes)
    }

def test_order_number_generation():
    """测试订单号生成性能"""
    # 测试 10 次生成
    times = []
    order_numbers = []
    
    for i in range(10):
        start = time.time()
        order_number = WorkOrder.generate_order_number()
        end = time.time()
        elapsed = (end - start) * 1000
        times.append(elapsed)
        order_numbers.append(order_number)
    
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    return {
        'name': '订单号生成性能',
        'avg_ms': avg_time,
        'min_ms': min_time,
        'max_ms': max_time,
        'order_numbers': order_numbers
    }


def main():
    """主测试函数"""
    try:
        # 检查数据量
        workorder_count = WorkOrder.objects.count()
        task_count = WorkOrderTask.objects.count()
        process_count = WorkOrderProcess.objects.count()
        
        if workorder_count == 0:
            return {'error': '无施工单数据'}
        
        # 执行测试
        results = []
        results.append(test_workorder_list_performance())
        results.append(test_task_list_performance())
        results.append(test_index_usage())
        results.append(test_order_number_generation())
        
        return {'results': results, 'status': 'success'}
        
    except Exception as e:
        return {'error': str(e)}


if __name__ == '__main__':
    main()
