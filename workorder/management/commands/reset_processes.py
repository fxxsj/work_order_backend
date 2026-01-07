"""
重置工序数据的管理命令
运行: python manage.py reset_processes
功能：
1. 清空所有工序数据（包括关联数据）
2. 从共享数据源加载21个标准工序
3. 这些工序的code字段在Admin中为只读
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from workorder.models import Process, WorkOrderProcess, Product
from workorder.data import PRESET_PROCESSES


class Command(BaseCommand):
    help = '重置工序数据：清空现有工序并加载预设的21个标准工序'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制执行，即使有施工单在使用这些工序',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        
        # 检查是否有施工单在使用工序
        work_order_processes_count = WorkOrderProcess.objects.count()
        if work_order_processes_count > 0 and not force:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠ 发现 {work_order_processes_count} 个施工单工序记录正在使用工序数据。'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    '如果继续，这些施工单工序记录将被删除。'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    '使用 --force 参数强制执行，或先处理这些施工单数据。'
                )
            )
            return
        
        # 检查产品默认工序关联
        products_with_processes = Product.objects.filter(default_processes__isnull=False).distinct()
        products_count = products_with_processes.count()
        if products_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠ 发现 {products_count} 个产品关联了默认工序，这些关联将被清除。'
                )
            )
        
        try:
            with transaction.atomic():
                # 1. 清除产品默认工序关联
                self.stdout.write('正在清除产品默认工序关联...')
                for product in products_with_processes:
                    product.default_processes.clear()
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 已清除 {products_count} 个产品的默认工序关联')
                )
                
                # 2. 删除施工单工序记录（如果force=True）
                if force and work_order_processes_count > 0:
                    self.stdout.write('正在删除施工单工序记录...')
                    WorkOrderProcess.objects.all().delete()
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ 已删除 {work_order_processes_count} 个施工单工序记录')
                    )
                
                # 3. 删除所有现有工序
                self.stdout.write('正在删除现有工序...')
                process_count = Process.objects.count()
                Process.objects.all().delete()
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 已删除 {process_count} 个现有工序')
                )
                
                # 4. 加载预设工序数据（使用共享数据源）
                self.stdout.write('正在加载预设工序数据...')
                try:
                    for process_data in PRESET_PROCESSES:
                        Process.objects.create(**process_data)
                    loaded_count = Process.objects.count()
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ 成功加载 {loaded_count} 个预设工序')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ 加载预设数据失败: {e}')
                    )
                    raise
                
                self.stdout.write('')
                self.stdout.write(
                    self.style.SUCCESS('=' * 60)
                )
                self.stdout.write(
                    self.style.SUCCESS('工序数据重置完成！')
                )
                self.stdout.write('')
                self.stdout.write('预设的21个工序已加载，code字段在Admin中为只读。')
                self.stdout.write('')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ 重置失败: {e}')
            )
            raise

