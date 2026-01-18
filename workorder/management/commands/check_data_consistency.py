from django.core.management.base import BaseCommand
from workorder.services.data_consistency import DataConsistencyManager


class Command(BaseCommand):
    help = '检查和修复数据一致性问题'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-type',
            type=str,
            default='all',
            choices=['stock', 'quantity', 'material', 'all'],
            help='检查类型: stock(库存), quantity(数量), material(物料), all(全部)'
        )
        
        parser.add_argument(
            '--fix',
            action='store_true',
            help='自动修复发现的问题'
        )
        
        parser.add_argument(
            '--fix-type',
            type=str,
            default='all',
            choices=['stock', 'quantity', 'all'],
            help='修复类型: stock(库存), quantity(数量), all(全部)'
        )

    def handle(self, *args, **options):
        check_type = options['check_type']
        auto_fix = options['fix']
        fix_type = options['fix_type']
        
        self.stdout.write(f"开始数据一致性检查，类型: {check_type}")
        
        # 执行检查
        check_results = DataConsistencyManager.run_consistency_check(check_type)
        
        # 显示检查结果
        self._display_check_results(check_results)
        
        # 自动修复
        if auto_fix:
            self.stdout.write(f"\n开始自动修复问题，类型: {fix_type}")
            fix_results = DataConsistencyManager.auto_fix_consistency_issues(fix_type)
            self._display_fix_results(fix_results)
        
        self.stdout.write("\n数据一致性检查完成")

    def _display_check_results(self, results):
        """显示检查结果"""
        check_time = results['check_time']
        self.stdout.write(f"\n检查时间: {check_time}")
        
        for check_type, data in results['results'].items():
            self.stdout.write(f"\n=== {check_type.upper()} 检查结果 ===")
            
            if check_type == 'stock':
                self.stdout.write(f"总产品数: {data['total_products']}")
                self.stdout.write(f"不一致产品数: {data['inconsistent_count']}")
                
                if data['inconsistent_products']:
                    self.stdout.write("\n不一致的产品:")
                    for item in data['inconsistent_products']:
                        product = item['product']
                        issues = item['validation']['issues']
                        self.stdout.write(f"  - {product.code}: {', '.join(issues)}")
            
            elif check_type == 'quantity':
                self.stdout.write(f"总施工单数: {data['total_orders']}")
                self.stdout.write(f"不一致施工单数: {data['inconsistent_count']}")
                
                if data['inconsistent_orders']:
                    self.stdout.write("\n不一致的施工单:")
                    for item in data['inconsistent_orders']:
                        order = item['work_order']
                        issues = item['validation']['issues']
                        self.stdout.write(f"  - {order.order_number}: {', '.join(issues)}")
            
            elif check_type == 'material':
                self.stdout.write(f"活跃施工单数: {data['active_orders']}")
                self.stdout.write(f"有物料问题的施工单数: {data['orders_with_issues']}")
                
                if data['material_issues']:
                    self.stdout.write("\n物料问题:")
                    for item in data['material_issues']:
                        order = item['work_order']
                        issues = item['issues']
                        self.stdout.write(f"  - {order.order_number}: {', '.join(issues)}")

    def _display_fix_results(self, results):
        """显示修复结果"""
        fix_time = results['fix_time']
        self.stdout.write(f"\n修复时间: {fix_time}")
        
        for fix_type, data in results['results'].items():
            self.stdout.write(f"\n=== {fix_type.upper()} 修复结果 ===")
            
            if fix_type == 'stock':
                self.stdout.write(f"检查总数: {data['total_checked']}")
                self.stdout.write(f"修复成功: {data['fixed_count']}")
                self.stdout.write(f"修复失败: {data['failed_count']}")
                
                if data['fix_details']:
                    self.stdout.write("\n修复详情:")
                    for detail in data['fix_details']:
                        product_code = detail['product_code']
                        changes = detail['changes']
                        for change in changes:
                            if change['type'] == 'stock_fix':
                                self.stdout.write(
                                    f"  - {product_code}: "
                                    f"{change['old_quantity']} -> {change['new_quantity']} "
                                    f"(差异: {change['difference']})"
                                )
            
            elif fix_type == 'quantity':
                self.stdout.write(f"检查总数: {data['total_checked']}")
                self.stdout.write(f"不一致数量: {data['inconsistent_count']}")
                self.stdout.write(f"需要人工审核: {'是' if data['requires_manual_review'] else '否'}")
                
                if data['inconsistent_orders']:
                    self.stdout.write("\n需要人工审核的施工单:")
                    for item in data['inconsistent_orders']:
                        order_number = item['order_number']
                        issues = item['issues']
                        self.stdout.write(f"  - {order_number}: {', '.join(issues)}")
                    self.stdout.write("\n注意: 数量一致性问题需要人工审核，请检查相关施工单")