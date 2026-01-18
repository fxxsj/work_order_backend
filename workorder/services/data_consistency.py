"""
数据一致性服务

解决库存管理和数量统计的一致性问题：
1. 统一数量概念和计算逻辑
2. 确保库存更新的原子性
3. 实现库存预警和自动补货
4. 提供数据一致性检查和修复
"""

from django.db import transaction
from django.db.models import F, Sum, Q, Count
from django.utils import timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class StockConsistencyService:
    """库存一致性服务"""
    
    @staticmethod
    def calculate_work_order_production_quantity(work_order) -> Dict[int, int]:
        """
        计算施工单的实际生产数量
        
        Returns:
            Dict[int, int]: {product_id: actual_quantity}
        """
        product_quantities = {}
        
        # 获取所有已完成的任务
        completed_tasks = work_order.order_processes.filter(
            tasks__status='completed'
        ).prefetch_related('tasks')
        
        for process in completed_tasks:
            for task in process.tasks.filter(status='completed'):
                if task.product and task.quantity_completed:
                    product_id = task.product.id
                    if product_id not in product_quantities:
                        product_quantities[product_id] = 0
                    product_quantities[product_id] += task.quantity_completed
        
        return product_quantities
    
    @staticmethod
    def validate_stock_consistency(product) -> Dict[str, any]:
        """
        验证产品库存一致性
        
        Returns:
            Dict: {
                'is_consistent': bool,
                'expected_quantity': int,
                'actual_quantity': int,
                'difference': int,
                'issues': List[str]
            }
        """
        from ..models.products import ProductStockLog
        
        # 获取当前库存数量
        actual_quantity = product.stock_quantity
        
        # 计算预期库存数量
        logs = ProductStockLog.objects.filter(product=product)
        expected_quantity = 0
        
        for log in logs:
            expected_quantity += log.quantity
        
        issues = []
        difference = actual_quantity - expected_quantity
        
        if difference != 0:
            issues.append(f"库存数量不一致：实际{actual_quantity}，预期{expected_quantity}，差异{difference}")
        
        # 检查库存日志完整性
        if not logs.exists():
            issues.append("缺少库存变更日志")
        
        # 检查负库存
        if actual_quantity < 0:
            issues.append(f"库存为负数：{actual_quantity}")
        
        return {
            'is_consistent': len(issues) == 0,
            'expected_quantity': expected_quantity,
            'actual_quantity': actual_quantity,
            'difference': difference,
            'issues': issues,
            'last_log': logs.first() if logs.exists() else None
        }
    
    @staticmethod
    @transaction.atomic
    def fix_stock_consistency(product, user=None) -> Dict[str, any]:
        """
        修复产品库存一致性
        
        Returns:
            Dict: 修复结果信息
        """
        from ..models.products import ProductStockLog
        
        validation = StockConsistencyService.validate_stock_consistency(product)
        
        if validation['is_consistent']:
            return {
                'success': True,
                'message': '库存数据一致，无需修复',
                'changes': []
            }
        
        old_quantity = product.stock_quantity
        expected_quantity = validation['expected_quantity']
        
        # 更新库存数量
        product.stock_quantity = expected_quantity
        product.save(update_fields=['stock_quantity'])
        
        # 创建修复日志
        fix_log = ProductStockLog.objects.create(
            product=product,
            change_type='add' if expected_quantity > old_quantity else 'reduce',
            quantity=expected_quantity - old_quantity,
            old_quantity=old_quantity,
            new_quantity=expected_quantity,
            reason=f'系统自动修复库存不一致，原数量：{old_quantity}，修复后：{expected_quantity}',
            created_by=user
        )
        
        logger.info(f"产品 {product.code} 库存一致性已修复：{old_quantity} -> {expected_quantity}")
        
        return {
            'success': True,
            'message': '库存一致性修复完成',
            'changes': [{
                'type': 'stock_fix',
                'old_quantity': old_quantity,
                'new_quantity': expected_quantity,
                'difference': expected_quantity - old_quantity,
                'log_id': fix_log.id
            }]
        }


class WorkOrderQuantityService:
    """施工单数量管理服务"""
    
    @staticmethod
    def get_quantity_summary(work_order) -> Dict[str, any]:
        """
        获取施工单数量汇总信息
        
        Returns:
            Dict: 包含各种数量概念的汇总
        """
        # 施工单数量（原始订单数量）
        order_quantity = work_order.production_quantity or 0
        
        # 产品数量汇总
        product_items = work_order.products.all()
        total_product_quantity = sum(item.quantity or 0 for item in product_items)
        
        # 任务完成数量汇总
        completed_tasks = work_order.order_processes.filter(
            tasks__status='completed'
        ).prefetch_related('tasks')
        
        task_quantities = {}
        total_task_quantity = 0
        total_defective_quantity = 0
        
        for process in completed_tasks:
            for task in process.tasks.filter(status='completed'):
                if task.quantity_completed:
                    task_type = task.task_type
                    if task_type not in task_quantities:
                        task_quantities[task_type] = 0
                    task_quantities[task_type] += task.quantity_completed
                    total_task_quantity += task.quantity_completed
                
                if task.quantity_defective:
                    total_defective_quantity += task.quantity_defective
        
        # 工序完成数量汇总
        process_quantities = {}
        total_process_quantity = 0
        
        for process in work_order.order_processes.all():
            if process.quantity_completed:
                process_code = process.process.code
                if process_code not in process_quantities:
                    process_quantities[process_code] = 0
                process_quantities[process_code] += process.quantity_completed
                total_process_quantity += process.quantity_completed
        
        return {
            'order_quantity': order_quantity,
            'total_product_quantity': total_product_quantity,
            'total_task_quantity': total_task_quantity,
            'total_process_quantity': total_process_quantity,
            'total_defective_quantity': total_defective_quantity,
            'task_quantities_by_type': task_quantities,
            'process_quantities_by_code': process_quantities,
            'quantity_consistency': {
                'order_vs_product': order_quantity == total_product_quantity,
                'order_vs_task': order_quantity == total_task_quantity,
                'task_vs_process': total_task_quantity == total_process_quantity
            }
        }
    
    @staticmethod
    def validate_quantity_consistency(work_order) -> Dict[str, any]:
        """
        验证施工单数量一致性
        
        Returns:
            Dict: 验证结果
        """
        summary = WorkOrderQuantityService.get_quantity_summary(work_order)
        issues = []
        
        # 检查施工单数量与产品数量一致性
        if summary['order_quantity'] != summary['total_product_quantity']:
            issues.append(
                f"施工单数量({summary['order_quantity']})与产品数量汇总({summary['total_product_quantity']})不一致"
            )
        
        # 检查任务数量一致性
        if summary['order_quantity'] != summary['total_task_quantity']:
            issues.append(
                f"施工单数量({summary['order_quantity']})与任务完成数量汇总({summary['total_task_quantity']})不一致"
            )
        
        # 检查工序数量一致性
        if summary['total_task_quantity'] != summary['total_process_quantity']:
            issues.append(
                f"任务完成数量({summary['total_task_quantity']})与工序完成数量({summary['total_process_quantity']})不一致"
            )
        
        # 检查负数量
        if summary['order_quantity'] < 0:
            issues.append(f"施工单数量为负数：{summary['order_quantity']}")
        
        if summary['total_defective_quantity'] < 0:
            issues.append(f"不良品数量为负数：{summary['total_defective_quantity']}")
        
        return {
            'is_consistent': len(issues) == 0,
            'summary': summary,
            'issues': issues
        }


class MaterialStockService:
    """物料库存管理服务"""
    
    @staticmethod
    def calculate_material_usage(work_order) -> Dict[int, Dict[str, any]]:
        """
        计算施工单的物料使用情况
        
        Returns:
            Dict[int, Dict]: {material_id: usage_info}
        """
        material_usage = {}
        
        # 获取施工单中的物料配置
        for material_item in work_order.materials.all():
            material_id = material_item.material.id
            usage_info = {
                'material': material_item.material,
                'planned_usage': material_item.material_usage,
                'need_cutting': material_item.need_cutting,
                'purchase_status': material_item.purchase_status,
                'actual_usage': 0,
                'waste_quantity': 0
            }
            
            # 计算实际使用量（基于开料任务）
            cutting_tasks = work_order.order_processes.filter(
                process__code='CUT'
            ).prefetch_related('tasks').first()
            
            if cutting_tasks:
                for task in cutting_tasks.tasks.filter(
                    material=material_item.material,
                    status='completed'
                ):
                    usage_info['actual_usage'] += task.quantity_completed or 0
                    if task.quantity_defective:
                        usage_info['waste_quantity'] += task.quantity_defective
            
            material_usage[material_id] = usage_info
        
        return material_usage
    
    @staticmethod
    def check_material_availability(work_order) -> Dict[str, any]:
        """
        检查物料可用性
        
        Returns:
            Dict: 检查结果
        """
        material_usage = MaterialStockService.calculate_material_usage(work_order)
        issues = []
        warnings = []
        
        for material_id, usage_info in material_usage.items():
            material = usage_info['material']
            
            # 检查采购状态
            if usage_info['purchase_status'] in ['pending', 'ordered']:
                issues.append(f"物料 {material.name} 尚未到货")
            
            # 检查开料状态
            if usage_info['need_cutting'] and usage_info['purchase_status'] != 'cut':
                issues.append(f"物料 {material.name} 需要开料但尚未开料")
            
            # 检查库存（如果有库存管理）
            if hasattr(material, 'stock_quantity'):
                if material.stock_quantity < usage_info['actual_usage']:
                    issues.append(
                        f"物料 {material.name} 库存不足：需要{usage_info['actual_usage']}，库存{material.stock_quantity}"
                    )
        
        return {
            'is_available': len(issues) == 0,
            'material_usage': material_usage,
            'issues': issues,
            'warnings': warnings
        }


class DataConsistencyManager:
    """数据一致性管理器"""
    
    @staticmethod
    def run_consistency_check(check_type: str = 'all') -> Dict[str, any]:
        """
        运行数据一致性检查
        
        Args:
            check_type: 检查类型 ('stock', 'quantity', 'material', 'all')
        
        Returns:
            Dict: 检查结果
        """
        results = {
            'check_time': timezone.now(),
            'results': {}
        }
        
        if check_type in ['stock', 'all']:
            results['results']['stock'] = DataConsistencyManager._check_stock_consistency()
        
        if check_type in ['quantity', 'all']:
            results['results']['quantity'] = DataConsistencyManager._check_quantity_consistency()
        
        if check_type in ['material', 'all']:
            results['results']['material'] = DataConsistencyManager._check_material_consistency()
        
        return results
    
    @staticmethod
    def _check_stock_consistency() -> Dict[str, any]:
        """检查库存一致性"""
        from ..models.products import Product
        
        products = Product.objects.all()
        inconsistent_products = []
        
        for product in products:
            validation = StockConsistencyService.validate_stock_consistency(product)
            if not validation['is_consistent']:
                inconsistent_products.append({
                    'product': product,
                    'validation': validation
                })
        
        return {
            'total_products': products.count(),
            'inconsistent_count': len(inconsistent_products),
            'inconsistent_products': inconsistent_products
        }
    
    @staticmethod
    def _check_quantity_consistency() -> Dict[str, any]:
        """检查数量一致性"""
        from ..models.core import WorkOrder
        
        work_orders = WorkOrder.objects.all()
        inconsistent_orders = []
        
        for work_order in work_orders:
            validation = WorkOrderQuantityService.validate_quantity_consistency(work_order)
            if not validation['is_consistent']:
                inconsistent_orders.append({
                    'work_order': work_order,
                    'validation': validation
                })
        
        return {
            'total_orders': work_orders.count(),
            'inconsistent_count': len(inconsistent_orders),
            'inconsistent_orders': inconsistent_orders
        }
    
    @staticmethod
    def _check_material_consistency() -> Dict[str, any]:
        """检查物料一致性"""
        from ..models.core import WorkOrder
        
        work_orders = WorkOrder.objects.filter(status__in=['in_progress', 'pending'])
        material_issues = []
        
        for work_order in work_orders:
            availability = MaterialStockService.check_material_availability(work_order)
            if not availability['is_available']:
                material_issues.append({
                    'work_order': work_order,
                    'issues': availability['issues']
                })
        
        return {
            'active_orders': work_orders.count(),
            'orders_with_issues': len(material_issues),
            'material_issues': material_issues
        }
    
    @staticmethod
    def auto_fix_consistency_issues(fix_type: str = 'all', user=None) -> Dict[str, any]:
        """
        自动修复一致性问题
        
        Args:
            fix_type: 修复类型 ('stock', 'quantity', 'all')
            user: 执行修复的用户
        
        Returns:
            Dict: 修复结果
        """
        results = {
            'fix_time': timezone.now(),
            'results': {}
        }
        
        if fix_type in ['stock', 'all']:
            results['results']['stock'] = DataConsistencyManager._fix_stock_issues(user)
        
        if fix_type in ['quantity', 'all']:
            results['results']['quantity'] = DataConsistencyManager._fix_quantity_issues(user)
        
        return results
    
    @staticmethod
    def _fix_stock_issues(user=None) -> Dict[str, any]:
        """修复库存问题"""
        from ..models.products import Product
        
        products = Product.objects.all()
        fixed_count = 0
        failed_count = 0
        fix_details = []
        
        for product in products:
            validation = StockConsistencyService.validate_stock_consistency(product)
            if not validation['is_consistent']:
                try:
                    result = StockConsistencyService.fix_stock_consistency(product, user)
                    if result['success']:
                        fixed_count += 1
                        fix_details.append({
                            'product_code': product.code,
                            'changes': result['changes']
                        })
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"修复产品 {product.code} 库存失败: {str(e)}")
                    failed_count += 1
        
        return {
            'total_checked': products.count(),
            'fixed_count': fixed_count,
            'failed_count': failed_count,
            'fix_details': fix_details
        }
    
    @staticmethod
    def _fix_quantity_issues(user=None) -> Dict[str, any]:
        """修复数量问题"""
        from ..models.core import WorkOrder
        
        # 数量一致性通常需要人工审核，这里只记录问题
        work_orders = WorkOrder.objects.all()
        inconsistent_orders = []
        
        for work_order in work_orders:
            validation = WorkOrderQuantityService.validate_quantity_consistency(work_order)
            if not validation['is_consistent']:
                inconsistent_orders.append({
                    'order_number': work_order.order_number,
                    'issues': validation['issues']
                })
        
        return {
            'total_checked': work_orders.count(),
            'inconsistent_count': len(inconsistent_orders),
            'inconsistent_orders': inconsistent_orders,
            'requires_manual_review': True
        }