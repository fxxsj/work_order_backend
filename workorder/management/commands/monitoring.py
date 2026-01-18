"""
监控管理命令

提供性能监控、业务指标收集、健康检查等功能
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import json

from workorder.services.monitoring import monitoring_service, BusinessMetrics, PerformanceMonitor


class Command(BaseCommand):
    help = '系统监控管理命令'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['collect', 'health', 'performance', 'business', 'cleanup'],
            default='collect',
            help='监控操作类型'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='输出文件路径（可选）'
        )
        parser.add_argument(
            '--time-range',
            type=str,
            choices=['1h', '24h', '7d', '30d'],
            default='24h',
            help='时间范围'
        )
    
    def handle(self, *args, **options):
        action = options['action']
        
        self.stdout.write(self.style.SUCCESS(f'执行监控操作: {action}'))
        
        if action == 'collect':
            self.collect_metrics(options)
        elif action == 'health':
            self.health_check(options)
        elif action == 'performance':
            self.performance_check(options)
        elif action == 'business':
            self.business_metrics(options)
        elif action == 'cleanup':
            self.cleanup_metrics(options)
        
        self.stdout.write(self.style.SUCCESS('监控操作完成'))
    
    def collect_metrics(self, options):
        """收集所有指标"""
        self.stdout.write('收集系统指标...')
        
        metrics = monitoring_service.get_dashboard_metrics()
        
        if options.get('output'):
            # 输出到文件
            with open(options['output'], 'w', encoding='utf-8') as f:
                json.dump(metrics, f, ensure_ascii=False, indent=2, default=str)
            self.stdout.write(self.style.SUCCESS(f'指标已输出到: {options["output"]}'))
        else:
            # 输出到控制台
            self.stdout.write(json.dumps(metrics, ensure_ascii=False, indent=2, default=str))
    
    def health_check(self, options):
        """健康检查"""
        self.stdout.write('执行系统健康检查...')
        
        health = monitoring_service.health_check()
        
        status_colors = {
            'healthy': self.style.SUCCESS,
            'degraded': self.style.WARNING,
            'unhealthy': self.style.ERROR
        }
        
        color = status_colors.get(health['status'], self.style.WARNING)
        self.stdout.write(f"系统状态: {color(health['status'])}")
        
        for check_name, check_result in health['checks'].items():
            if check_result['status'] == 'ok':
                self.stdout.write(f"  ✓ {check_name}: 正常")
            else:
                self.stdout.write(f"  ✗ {check_name}: {check_result.get('error', '异常')}")
        
        # 输出结果
        if options.get('output'):
            with open(options['output'], 'w', encoding='utf-8') as f:
                json.dump(health, f, ensure_ascii=False, indent=2, default=str)
            self.stdout.write(self.style.SUCCESS(f'健康检查结果已输出到: {options["output"]}'))
    
    def performance_check(self, options):
        """性能检查"""
        self.stdout.write('检查系统性能...')
        
        stats = monitoring_service.performance_monitor.get_performance_stats()
        
        self.stdout.write(f"总请求数: {stats['total_requests']}")
        self.stdout.write(f"平均响应时间: {stats['avg_response_time']:.3f}s")
        self.stdout.write(f"慢查询数: {stats['slow_queries']}")
        self.stdout.write(f"错误数: {stats['errors']}")
        self.stdout.write(f"错误率: {stats['error_rate']:.2f}%")
        
        # 检查性能告警条件
        warnings = []
        
        if stats['avg_response_time'] > 2.0:
            warnings.append('平均响应时间过长')
        
        if stats['error_rate'] > 5.0:
            warnings.append('错误率过高')
        
        if stats['slow_queries'] > 10:
            warnings.append('慢查询过多')
        
        if warnings:
            self.stdout.write(self.style.WARNING(f"性能警告: {', '.join(warnings)}"))
        else:
            self.stdout.write(self.style.SUCCESS('性能指标正常'))
        
        # 输出最慢的端点
        if stats['slowest_endpoints']:
            self.stdout.write('\n最慢的端点:')
            for i, endpoint in enumerate(stats['slowest_endpoints'][:5], 1):
                self.stdout.write(f"  {i}. {endpoint['name']}: {endpoint['execution_time']:.3f}s")
    
    def business_metrics(self, options):
        """业务指标检查"""
        time_range = options.get('time_range', '24h')
        self.stdout.write(f'获取业务指标 ({time_range})...')
        
        # 施工单指标
        workorder_metrics = BusinessMetrics.get_workorder_metrics(time_range)
        self.stdout.write(f"  施工单总数: {workorder_metrics['order_stats']['total']}")
        self.stdout.write(f"  完成率: {workorder_metrics['order_stats']['completion_rate']:.1f}%")
        self.stdout.write(f"  审核通过率: {workorder_metrics['approval_stats']['approval_rate']:.1f}%")
        self.stdout.write(f"  平均完成天数: {workorder_metrics['time_metrics']['avg_completion_days']:.1f}天")
        
        # 任务指标
        task_metrics = BusinessMetrics.get_task_metrics(time_range)
        self.stdout.write(f"  任务总数: {task_metrics['task_stats']['total']}")
        self.stdout.write(f"  任务完成率: {task_metrics['task_stats']['completion_rate']:.1f}%")
        self.stdout.write(f"  超时任务数: {task_metrics['time_metrics']['overdue_tasks']}")
        self.stdout.write(f"  超时率: {task_metrics['time_metrics']['overdue_rate']:.1f}%")
        
        # 系统指标
        system_metrics = BusinessMetrics.get_system_metrics()
        self.stdout.write(f"  CPU使用率: {system_metrics['system_resources']['cpu_percent']:.1f}%")
        self.stdout.write(f"  内存使用率: {system_metrics['system_resources']['memory_percent']:.1f}%")
        self.stdout.write(f"  磁盘使用率: {system_metrics['system_resources']['disk_percent']:.1f}%")
        
        # 检查业务告警条件
        warnings = []
        
        if workorder_metrics['time_metrics']['orders_overdue'] > 10:
            warnings.append('逾期订单过多')
        
        if task_metrics['task_stats']['completion_rate'] < 80:
            warnings.append('任务完成率过低')
        
        if system_metrics['system_resources']['cpu_percent'] > 80:
            warnings.append('CPU使用率过高')
        
        if system_metrics['system_resources']['memory_percent'] > 80:
            warnings.append('内存使用率过高')
        
        if warnings:
            self.stdout.write(self.style.WARNING(f"业务警告: {', '.join(warnings)}"))
        else:
            self.stdout.write(self.style.SUCCESS('业务指标正常'))
    
    def cleanup_metrics(self, options):
        """清理历史指标数据"""
        self.stdout.write('清理历史指标数据...')
        
        # 清理性能监控数据（保留最近1000条记录）
        perf_monitor = monitoring_service.performance_monitor
        
        for key in ['execution_times', 'slow_queries', 'errors']:
            if key in perf_monitor.metrics:
                data = perf_monitor.metrics[key]
                if len(data) > 1000:
                    perf_monitor.metrics[key] = data[-1000:]
                    self.stdout.write(f"  清理 {key}: 保留最新1000条记录")
        
        # 清理旧的缓存数据
        from django.core.cache import cache
        try:
            # 这里可以添加更复杂的缓存清理逻辑
            cache.delete_many([
                'perf:slow_queries:alert_sent',
                'alerts:business:last_check',
                'alerts:system:last_check'
            ])
            self.stdout.write('  清理缓存告警标记')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'缓存清理失败: {e}'))
        
        self.stdout.write(self.style.SUCCESS('历史指标数据清理完成'))