from django.core.management.base import BaseCommand
from monitoring.working_monitor import (
    get_performance_stats, 
    generate_performance_report,
    metrics,
    health_monitor
)
import json
from datetime import datetime

class Command(BaseCommand):
    help = 'Performance monitoring and reporting'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            default='table',
            choices=['table', 'json'],
            help='Output format'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed statistics'
        )

    def handle(self, *args, **options):
        format_type = options['format']
        detailed = options['detailed']
        
        # 获取性能报告
        report = generate_performance_report()
        
        if format_type == 'json':
            output = json.dumps(report, indent=2, default=str)
            self.stdout.write(output)
        else:
            self.print_table_report(report, detailed)
        
        # 检查告警
        alerts = report.get('alerts', [])
        if alerts:
            self.stdout.write(self.style.WARNING(f"\n🚨 Active Alerts: {len(alerts)}"))
            for alert in alerts:
                self.stdout.write(
                    self.style.ERROR(f"  {alert['severity'].upper()}: {alert['message']}")
                )
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ No active alerts"))
    
    def print_table_report(self, report, detailed):
        """打印表格格式的报告"""
        self.stdout.write(self.style.SUCCESS("=== Performance Monitoring Report ==="))
        self.stdout.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 系统健康状态
        health = report.get('health', {})
        self.stdout.write(f"\n🖥️  System Uptime: {health.get('uptime', 0):.1f}s")
        
        # 数据库状态
        db_stats = health.get('database', {}).get('stats', {})
        if db_stats:
            self.stdout.write(f"\n📊 Database Stats:")
            self.stdout.write(f"  Total Queries: {db_stats.get('total_queries', 0)}")
            self.stdout.write(f"  Slow Queries: {db_stats.get('slow_queries', 0)}")
            self.stdout.write(f"  Avg Query Time: {db_stats.get('avg_query_time', 0):.3f}s")
        
        # 性能指标
        metrics_data = report.get('metrics', {})
        if metrics_data:
            self.stdout.write(f"\n⚡ Performance Metrics:")
            for name, stats in metrics_data.items():
                if stats and stats.get('count', 0) > 0:
                    self.stdout.write(f"  {name}:")
                    self.stdout.write(f"    Count: {stats['count']}")
                    self.stdout.write(f"    Avg: {stats['avg']:.3f}s")
                    self.stdout.write(f"    Min: {stats['min']:.3f}s")
                    self.stdout.write(f"    Max: {stats['max']:.3f}s")
                    
                    if detailed:
                        self.stdout.write(f"    Recent: {[f'{x:.3f}s' for x in stats['recent']]}")
        
        # 错误计数
        counters = metrics.counters if hasattr(metrics, 'counters') else {}
        error_counters = {k: v for k, v in counters.items() if 'error' in k}
        if error_counters:
            self.stdout.write(f"\n❌ Error Counters:")
            for name, count in error_counters.items():
                if count > 0:
                    self.stdout.write(f"  {name}: {count}")
        
        # 成功计数
        success_counters = {k: v for k, v in counters.items() if 'success' in k}
        if success_counters:
            self.stdout.write(f"\n✅ Success Counters:")
            for name, count in success_counters.items():
                self.stdout.write(f"  {name}: {count}")