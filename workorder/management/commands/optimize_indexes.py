"""
数据库索引优化管理命令

为提升查询性能，创建必要的数据库索引：
1. 优化常用查询字段的单列索引
2. 创建复合索引支持多字段查询
3. 分析查询性能并提供优化建议
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.models import Index
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '优化数据库索引以提升查询性能'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅显示将要创建的索引，不实际执行'
        )
        
        parser.add_argument(
            '--analyze',
            action='store_true',
            help='分析现有查询性能'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        analyze = options['analyze']
        
        if analyze:
            self.analyze_query_performance()
        else:
            self.optimize_indexes(dry_run)

    def optimize_indexes(self, dry_run=False):
        """优化数据库索引"""
        self.stdout.write("开始数据库索引优化...")
        
        # 定义要创建的索引
        indexes_to_create = self.get_required_indexes()
        
        if dry_run:
            self.stdout.write("=== DRY RUN - 将要创建的索引 ===")
            for index_info in indexes_to_create:
                self.stdout.write(f"表: {index_info['table']}, 索引: {index_info['index']}")
            return
        
        # 执行索引创建
        with transaction.atomic():
            created_count = 0
            for index_info in indexes_to_create:
                try:
                    self.create_index(index_info)
                    created_count += 1
                    self.stdout.write(f"✓ 创建索引: {index_info['table']}.{index_info['index']}")
                except Exception as e:
                    self.stdout.write(f"✗ 创建索引失败: {index_info['table']}.{index_info['index']} - {str(e)}")
        
        self.stdout.write(f"索引优化完成，共创建 {created_count} 个索引")

    def get_required_indexes(self):
        """获取需要的索引列表"""
        return [
            # 施工单相关索引
            {
                'table': 'workorder_workorder',
                'index': 'idx_workorder_status_priority_created',
                'fields': ['status', 'priority', 'created_at'],
                'type': 'composite'
            },
            {
                'table': 'workorder_workorder',
                'index': 'idx_workorder_customer_status',
                'fields': ['customer_id', 'status'],
                'type': 'composite'
            },
            {
                'table': 'workorder_workorder',
                'index': 'idx_workorder_approval_status_created',
                'fields': ['approval_status', 'created_at'],
                'type': 'composite'
            },
            {
                'table': 'workorder_workorder',
                'index': 'idx_workorder_delivery_date',
                'fields': ['delivery_date'],
                'type': 'single'
            },
            {
                'table': 'workorder_workorder',
                'index': 'idx_workorder_order_number',
                'fields': ['order_number'],
                'type': 'unique'
            },
            
            # 工序相关索引
            {
                'table': 'workorder_workorderprocess',
                'index': 'idx_workorderprocess_work_order_sequence',
                'fields': ['work_order_id', 'sequence'],
                'type': 'composite'
            },
            {
                'table': 'workorder_workorderprocess',
                'index': 'idx_workorderprocess_status_sequence',
                'fields': ['status', 'sequence'],
                'type': 'composite'
            },
            {
                'table': 'workorder_workorderprocess',
                'index': 'idx_workorderprocess_department',
                'fields': ['department_id'],
                'type': 'single'
            },
            {
                'table': 'workorder_workorderprocess',
                'index': 'idx_workorderprocess_operator',
                'fields': ['operator_id'],
                'type': 'single'
            },
            {
                'table': 'workorder_workorderprocess',
                'index': 'idx_workorderprocess_start_time',
                'fields': ['actual_start_time'],
                'type': 'single'
            },
            
            # 任务相关索引
            {
                'table': 'workorder_workordertask',
                'index': 'idx_workordertask_process_status',
                'fields': ['work_order_process_id', 'status'],
                'type': 'composite'
            },
            {
                'table': 'workorder_workordertask',
                'index': 'idx_workordertask_operator_status',
                'fields': ['assigned_operator_id', 'status'],
                'type': 'composite'
            },
            {
                'table': 'workorder_workordertask',
                'index': 'idx_workordertask_department_status',
                'fields': ['assigned_department_id', 'status'],
                'type': 'composite'
            },
            {
                'table': 'workorder_workordertask',
                'index': 'idx_workordertask_type_created',
                'fields': ['task_type', 'created_at'],
                'type': 'composite'
            },
            {
                'table': 'workorder_workordertask',
                'index': 'idx_workordertask_content',
                'fields': ['work_content'],
                'type': 'single'
            },
            
            # 产品相关索引
            {
                'table': 'workorder_product',
                'index': 'idx_product_code',
                'fields': ['code'],
                'type': 'unique'
            },
            {
                'table': 'workorder_product',
                'index': 'idx_product_stock_quantity',
                'fields': ['stock_quantity'],
                'type': 'single'
            },
            {
                'table': 'workorder_product',
                'index': 'idx_product_is_active',
                'fields': ['is_active'],
                'type': 'single'
            },
            
            # 物料相关索引
            {
                'table': 'workorder_material',
                'index': 'idx_material_code',
                'fields': ['code'],
                'type': 'unique'
            },
            {
                'table': 'workorder_material',
                'index': 'idx_material_status',
                'fields': ['status'],
                'type': 'single'
            },
            
            # 客户相关索引
            {
                'table': 'workorder_customer',
                'index': 'idx_customer_salesperson',
                'fields': ['salesperson_id'],
                'type': 'single'
            },
            {
                'table': 'workorder_customer',
                'index': 'idx_customer_name',
                'fields': ['name'],
                'type': 'single'
            },
            
            # 通知相关索引
            {
                'table': 'workorder_notification',
                'index': 'idx_notification_recipient_read',
                'fields': ['recipient_id', 'is_read'],
                'type': 'composite'
            },
            {
                'table': 'workorder_notification',
                'index': 'idx_notification_created_priority',
                'fields': ['created_at', 'priority'],
                'type': 'composite'
            },
            
            # 库存日志相关索引
            {
                'table': 'workorder_productstocklog',
                'index': 'idx_productstocklog_product_created',
                'fields': ['product_id', 'created_at'],
                'type': 'composite'
            },
            {
                'table': 'workorder_productstocklog',
                'index': 'idx_productstocklog_change_type',
                'fields': ['change_type'],
                'type': 'single'
            },
        ]

    def create_index(self, index_info):
        """创建单个索引"""
        table_name = index_info['table']
        index_name = index_info['index']
        fields = index_info['fields']
        index_type = index_info['type']
        
        with connection.cursor() as cursor:
            if index_type == 'unique':
                sql = f"""
                CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {index_name}
                ON {table_name} ({', '.join(fields)})
                """
            elif index_type == 'composite':
                sql = f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}
                ON {table_name} ({', '.join(fields)})
                """
            else:  # single column
                sql = f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}
                ON {table_name} ({fields[0]})
                """
            
            cursor.execute(sql)

    def analyze_query_performance(self):
        """分析查询性能"""
        self.stdout.write("开始查询性能分析...")
        
        # 启用查询日志记录（PostgreSQL）
        if 'postgresql' in connection.settings_dict['ENGINE']:
            with connection.cursor() as cursor:
                # 临时启用查询统计
                cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
                
                # 获取慢查询
                cursor.execute("""
                    SELECT 
                        query,
                        calls,
                        total_time,
                        mean_time,
                        rows
                    FROM pg_stat_statements 
                    WHERE mean_time > 100  -- 超过100ms的查询
                    ORDER BY mean_time DESC 
                    LIMIT 10
                """)
                
                slow_queries = cursor.fetchall()
                
                self.stdout.write("=== 慢查询分析 ===")
                for query in slow_queries:
                    self.stdout.write(
                        f"调用次数: {query[1]}, "
                        f"总时间: {query[2]:.2f}ms, "
                        f"平均时间: {query[3]:.2f}ms"
                    )
                    self.stdout.write(f"SQL: {query[0][:100]}...")
                    self.stdout.write("-" * 80)
        
        # 获取表大小和索引使用情况
        self.analyze_table_sizes()

    def analyze_table_sizes(self):
        """分析表大小和索引使用"""
        if 'postgresql' in connection.settings_dict['ENGINE']:
            with connection.cursor() as cursor:
                # 获取表大小
                cursor.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) AS size),
                        pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                    LIMIT 10
                """)
                
                tables = cursor.fetchall()
                
                self.stdout.write("\n=== 表大小分析 ===")
                for table in tables:
                    self.stdout.write(f"{table[0]}.{table[1]}: {table[2]} ({table[3]} bytes)")
                
                # 获取索引使用情况
                cursor.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        indexname,
                        idx_scan,
                        idx_tup_read,
                        idx_tup_fetch
                    FROM pg_stat_user_indexes 
                    WHERE schemaname = 'public'
                    ORDER BY idx_scan DESC
                    LIMIT 10
                """)
                
                indexes = cursor.fetchall()
                
                self.stdout.write("\n=== 索引使用情况 ===")
                for index in indexes:
                    self.stdout.write(
                        f"{index[0]}.{index[1]}.{index[2]}: "
                        f"扫描{index[3]}次, 读取{index[4]}行, 获取{index[5]}行"
                    )
        else:
            self.stdout.write("查询性能分析仅支持 PostgreSQL 数据库")