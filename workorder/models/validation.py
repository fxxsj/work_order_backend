"""
施工单验证器

将 WorkOrder.validate_before_approval 的逻辑拆分为独立的验证器类。
"""

from django.utils import timezone
from django.db import models


class WorkOrderValidator:
    """
    施工单验证器
    
    将审核前的各种验证逻辑拆分为独立方法，提高可测试性和可维护性。
    
    使用示例:
        validator = WorkOrderValidator(work_order)
        errors = validator.validate_all()
        if errors:
            # 处理错误
    """
    
    def __init__(self, work_order):
        """
        初始化验证器
        
        Args:
            work_order: 要验证的 WorkOrder 实例
        """
        self.work_order = work_order
        self.errors = []
    
    def validate_all(self):
        """
        执行所有验证
        
        Returns:
            list: 错误信息列表，如果为空则表示验证通过
        """
        self.validate_basic_info()
        self.validate_asset_process_match()
        self.validate_quantities()
        self.validate_dates()
        self.validate_materials()
        self.validate_process_sequence()
        return self.errors
    
    def validate_basic_info(self):
        """
        验证基础信息（客户、产品、工序、交货日期）
        
        Returns:
            None: 错误会添加到 self.errors
        """
        # 检查客户信息
        if getattr(self.work_order, 'customer_id', None) is None:
            self.errors.append('缺少客户信息')
        
        # 检查产品信息
        if not self.work_order.products.exists():
            self.errors.append('缺少产品信息')
        
        # 检查工序信息
        if not self.work_order.order_processes.exists():
            self.errors.append('缺少工序信息')
        
        # 检查交货日期
        if not self.work_order.delivery_date:
            self.errors.append('缺少交货日期')
    
    def validate_asset_process_match(self):
        """
        验证版与工序匹配（图稿、刀模、烫金版、压凸版）
        
        确保选择的工序与所需的各种版（图稿、刀模等）匹配。
        """
        from workorder.models.base import Process
        
        # 获取所有选中的工序
        selected_processes = self.work_order.order_processes.values_list('process', flat=True)
        processes = Process.objects.filter(id__in=selected_processes, is_active=True)
        
        # 检查图稿
        processes_requiring_artwork = processes.filter(
            models.Q(requires_artwork=True) | models.Q(artwork_required=True)
        )
        if processes_requiring_artwork.exists() and not self.work_order.artworks.exists():
            process_names = ', '.join([p.name for p in processes_requiring_artwork])
            self.errors.append(f'选择了需要图稿的工序（{process_names}），请至少选择一个图稿')
        
        # 检查刀模
        processes_requiring_die = processes.filter(
            models.Q(requires_die=True) | models.Q(die_required=True)
        )
        if processes_requiring_die.exists() and not self.work_order.dies.exists():
            process_names = ', '.join([p.name for p in processes_requiring_die])
            self.errors.append(f'选择了需要刀模的工序（{process_names}），请至少选择一个刀模')
        
        # 检查烫金版
        processes_requiring_foiling_plate = processes.filter(
            requires_foiling_plate=True,
            foiling_plate_required=True
        )
        if processes_requiring_foiling_plate.exists() and not self.work_order.foiling_plates.exists():
            process_names = ', '.join([p.name for p in processes_requiring_foiling_plate])
            self.errors.append(f'选择了需要烫金版的工序（{process_names}），请至少选择一个烫金版')
        
        # 检查压凸版
        processes_requiring_embossing_plate = processes.filter(
            requires_embossing_plate=True,
            embossing_plate_required=True
        )
        if processes_requiring_embossing_plate.exists() and not self.work_order.embossing_plates.exists():
            process_names = ', '.join([p.name for p in processes_requiring_embossing_plate])
            self.errors.append(f'选择了需要压凸版的工序（{process_names}），请至少选择一个压凸版')
    
    def validate_quantities(self):
        """
        验证数量（生产数量、产品数量）
        """
        # 检查生产数量
        if self.work_order.production_quantity is None:
            self.errors.append('缺少生产数量')
        elif self.work_order.production_quantity <= 0:
            self.errors.append(
                f'生产数量必须大于0，当前值为{self.work_order.production_quantity}'
            )
        
        # 检查产品数量总和
        if self.work_order.products.exists():
            products = self.work_order.products.select_related('product').all()
            total_product_quantity = sum([p.quantity or 0 for p in products])
            if total_product_quantity <= 0:
                self.errors.append(
                    f'产品数量总和必须大于0，当前总和为{total_product_quantity}'
                )
    
    def validate_dates(self):
        """
        验证日期（交货日期合理性）
        """
        # 检查交货日期是否早于下单日期
        if self.work_order.delivery_date and self.work_order.order_date:
            order_date = self.work_order.order_date
            if hasattr(order_date, 'date'):
                order_date = order_date.date()
            
            if self.work_order.delivery_date < order_date:
                self.errors.append(
                    f'交货日期不能早于下单日期。'
                    f'交货日期：{self.work_order.delivery_date}，'
                    f'下单日期：{order_date}'
                )
        
        # 检查交货日期是否在过去（允许今天）
        today = timezone.now().date()
        if self.work_order.delivery_date and self.work_order.delivery_date < today:
            self.errors.append(
                f'交货日期不能早于今天。'
                f'交货日期：{self.work_order.delivery_date}，'
                f'今天：{today}'
            )
    
    def validate_materials(self):
        """
        验证物料（物料信息完整性、开料物料用量）
        """
        if not self.work_order.materials.exists():
            return
        
        materials = self.work_order.materials.select_related('material').all()
        for material_item in materials:
            if material_item.need_cutting and not material_item.material_usage:
                self.errors.append(
                    f'物料"{material_item.material.name}"需要开料，请填写物料用量'
                )
    
    def validate_process_sequence(self):
        """
        验证工序顺序（工序顺序合理性）
        
        确保制版在印刷之前，开料在印刷之前等。
        """
        processes_ordered = self.work_order.order_processes.filter(
            process__code__in=['CTP', 'PRT', 'CUT']
        ).select_related('process').order_by('sequence')
        
        ctp_sequence = None
        prt_sequence = None
        cut_sequence = None
        
        for wp in processes_ordered:
            if wp.process.code == 'CTP':
                ctp_sequence = wp.sequence
            elif wp.process.code == 'PRT':
                prt_sequence = wp.sequence
            elif wp.process.code == 'CUT':
                cut_sequence = wp.sequence
        
        if ctp_sequence is not None and prt_sequence is not None:
            if ctp_sequence > prt_sequence:
                self.errors.append(
                    '制版工序（CTP）应该在印刷工序（PRT）之前，请调整工序顺序'
                )
        
        if cut_sequence is not None and prt_sequence is not None:
            if cut_sequence > prt_sequence:
                self.errors.append(
                    '开料工序（CUT）应该在印刷工序（PRT）之前，请调整工序顺序'
                )
