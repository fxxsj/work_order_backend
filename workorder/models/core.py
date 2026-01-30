"""
核心业务模型

包含系统核心业务模型：
- APPROVED_ORDER_PROTECTED_FIELDS: 审核通过后禁止编辑的字段
- APPROVED_ORDER_EDITABLE_FIELDS: 审核通过后允许编辑的字段
- WorkOrder: 施工单
- WorkOrderProcess: 施工单工序
- WorkOrderProduct: 施工单产品
- WorkOrderMaterial: 施工单物料
- WorkOrderTask: 施工单任务
- ProcessLog: 工序日志
- TaskLog: 任务日志
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from django.db.models import Max
from datetime import datetime, date
import logging

# 配置日志记录器
logger = logging.getLogger(__name__)

# 导入 Process 和 Department 模型用于验证和分派
try:
    from workorder.models.base import Process, Department
except ImportError:
    # 如果在同一个模块中，使用相对导入
    from .base import Process, Department

# 审核通过后禁止编辑的核心字段列表
APPROVED_ORDER_PROTECTED_FIELDS = [
    'customer',           # 客户
    'products_data',      # 产品列表
    'processes',          # 工序列表
    'artworks',           # 图稿
    'dies',               # 刀模
    'foiling_plates',     # 烫金版
    'embossing_plates',   # 压凸版
    'printing_type',      # 印刷形式
    'printing_cmyk_colors',    # CMYK颜色
    'printing_other_colors',   # 其他颜色
    'production_quantity',     # 生产数量
    'total_amount',            # 总金额
]

# 审核通过后允许编辑的非核心字段列表
APPROVED_ORDER_EDITABLE_FIELDS = [
    'notes',                    # 备注
    'delivery_date',           # 交货日期
    'actual_delivery_date',    # 实际交货日期
    'priority',                # 优先级
    'design_file',             # 设计文件
    'materials',                # 物料信息（需要谨慎处理）
]

class WorkOrder(models.Model):
    """印刷施工单"""
    STATUS_CHOICES = [
        ('pending', '待开始'),
        ('in_progress', '进行中'),
        ('paused', '已暂停'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]

    PRIORITY_CHOICES = [
        ('low', '低'),
        ('normal', '普通'),
        ('high', '高'),
        ('urgent', '紧急'),
    ]

    order_number = models.CharField('施工单号', max_length=50, unique=True, editable=False)
    customer = models.ForeignKey('workorder.Customer', on_delete=models.PROTECT, verbose_name='客户')
    
    # 产品组关联（支持一个产品需要多个施工单的场景）
    product_group_item = models.ForeignKey('workorder.ProductGroupItem', on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='work_orders', verbose_name='产品组子项',
                                          help_text='如果该施工单是产品组的一部分，关联到对应的子产品')
    
    # 图稿、刀模、烫金版、压凸版关联（根据工序选择自动显示和验证）
    artworks = models.ManyToManyField('workorder.Artwork', blank=True,
                                      related_name='work_orders', verbose_name='图稿（CTP版）',
                                      help_text='关联的图稿，用于CTP制版，支持多个图稿（如纸卡双面印刷的面版和底版）')
    dies = models.ManyToManyField('workorder.Die', blank=True,
                                  related_name='work_orders', verbose_name='刀模',
                                  help_text='关联的刀模，用于模切工序，支持多个刀模')
    # 关联烫金版和压凸版
    foiling_plates = models.ManyToManyField('workorder.FoilingPlate', blank=True,
                                            related_name='work_orders', verbose_name='烫金版',
                                            help_text='关联的烫金版，用于烫金工序，支持多个烫金版')
    embossing_plates = models.ManyToManyField('workorder.EmbossingPlate', blank=True,
                                              related_name='work_orders', verbose_name='压凸版',
                                              help_text='关联的压凸版，用于压凸工序，支持多个压凸版')
    
    # 印刷形式
    PRINTING_TYPE_CHOICES = [
        ('none', '不需要印刷'),
        ('front', '正面印刷'),
        ('back', '背面印刷'),
        ('self_reverse', '自反印刷'),
        ('reverse_gripper', '反咬口印刷'),
        ('register', '套版印刷'),
    ]
    printing_type = models.CharField('印刷形式', max_length=20, choices=PRINTING_TYPE_CHOICES, 
                                    default='none', help_text='印刷形式，选择图稿时必选')
    printing_cmyk_colors = models.JSONField('印刷CMYK颜色', default=list, blank=True,
                                          help_text='选中的CMYK颜色，如：["C", "M", "K"]')
    printing_other_colors = models.JSONField('印刷其他颜色', default=list, blank=True,
                                           help_text='其他颜色列表，如：["528C", "金色"]')
    
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField('优先级', max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    order_date = models.DateField('下单日期', default=date.today)
    delivery_date = models.DateField('交货日期')
    actual_delivery_date = models.DateField('实际交货日期', null=True, blank=True)
    
    production_quantity = models.IntegerField('生产数量', null=True, blank=True, help_text='单位：车')
    defective_quantity = models.IntegerField('预损数量', null=True, blank=True, help_text='单位：车')
    
    total_amount = models.DecimalField('总金额', max_digits=12, decimal_places=2, default=0)
    
    # 文件附件
    design_file = models.FileField('设计文件', upload_to='designs/', blank=True, null=True)
    
    # 制表人（创建者）
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='managed_orders', verbose_name='制表人')
    
    notes = models.TextField('备注', blank=True)
    
    # 业务员审核相关字段
    APPROVAL_STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
    ]
    approval_status = models.CharField('审核状态', max_length=20, choices=APPROVAL_STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='approved_orders', verbose_name='审核人',
                                   help_text='业务员审核人')
    approved_at = models.DateTimeField('审核时间', null=True, blank=True)
    approval_comment = models.TextField('审核意见', blank=True, help_text='业务员审核意见')

    # 多级审核相关字段
    multi_level_approval_enabled = models.BooleanField(
        '是否启用多级审核',
        default=False,
        help_text='是否使用多级审核流程'
    )
    current_workflow = models.ForeignKey(
        'workorder.ApprovalWorkflow',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_workflow',
        verbose_name='当前审核工作流'
    )
    urgency_reason = models.TextField(
        '紧急原因',
        blank=True,
        help_text='标记为紧急订单的原因'
    )

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_orders', verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '施工单'
        verbose_name_plural = '施工单管理'
        ordering = ['-created_at']
        permissions = [
            ('change_approved_workorder', '可以编辑已审核的施工单'),
        ]
        # 添加索引以优化查询性能
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['approval_status']),
            models.Index(fields=['customer']),
            models.Index(fields=['manager']),
            models.Index(fields=['created_by']),
            models.Index(fields=['approved_by']),
            models.Index(fields=['order_date']),
            models.Index(fields=['delivery_date']),
            models.Index(fields=['status', 'priority']),  # 组合索引
            models.Index(fields=['customer', 'status']),  # 组合索引
            models.Index(fields=['approval_status', 'created_at']),  # 组合索引
        ]

    def __str__(self):
        # 显示第一个产品的名称，如果有多个产品则显示数量
        products = self.products.all()
        if products.exists():
            first_product = products.first()
            if products.count() > 1:
                return f"{self.order_number} - {first_product.product.name} 等{products.count()}款"
            return f"{self.order_number} - {first_product.product.name}"
        return f"{self.order_number}"

    def get_progress_percentage(self):
        """计算进度百分比"""
        total_processes = self.order_processes.count()
        if total_processes == 0:
            return 0
        completed_processes = self.order_processes.filter(status='completed').count()
        return int((completed_processes / total_processes) * 100)
    
    def validate_before_approval(self):
        """
        审核前验证施工单数据完整性

        使用 WorkOrderValidator 进行验证，提高代码可维护性和可测试性。

        验证内容：
        1. 基础信息验证（客户、产品、工序、交货日期）
        2. 版与工序匹配验证（图稿、刀模、烫金版、压凸版）
        3. 数量验证（生产数量、产品数量）
        4. 日期验证（交货日期合理性）
        5. 物料验证（物料信息完整性、开料物料用量）
        6. 工序顺序验证（工序顺序合理性）

        Returns:
            list: 错误信息列表，如果为空则表示验证通过
        """
        from .validation import WorkOrderValidator

        validator = WorkOrderValidator(self)
        return validator.validate_all()
    
    @classmethod
    def generate_order_number(cls):
        """生成施工单号：格式 yyyymm + 3位自增序号

        使用数据库事务和行锁确保并发安全，避免生成重复单号
        """
        from django.core.cache import cache
        from django.db import DatabaseError

        now = datetime.now()
        prefix = now.strftime('%Y%m')
        cache_key = f'order_number_{prefix}'

        # 使用数据库事务和行锁确保并发安全
        # 每次都从数据库获取最新序号，确保在高并发情况下也不会生成重复单号
        max_retries = 3  # 最大重试次数
        retry_count = 0

        while retry_count < max_retries:
            try:
                with transaction.atomic():
                    # 使用 select_for_update() 锁定查询结果，防止并发读取
                    last_order = cls.objects.filter(
                        order_number__startswith=prefix
                    ).order_by('-order_number').select_for_update().first()

                    if last_order:
                        # 提取序号部分
                        last_number = int(last_order.order_number[6:])
                    else:
                        # 当月第一单
                        last_number = 0

                    # 生成新序号
                    new_number = last_number + 1
                    order_number = f"{prefix}{new_number:03d}"

                    # 更新缓存以减少数据库查询（缓存仅作为优化，不依赖它保证并发安全）
                    cache.set(cache_key, new_number, 1800)

                    return order_number

            except DatabaseError as e:
                # 数据库错误（如死锁），进行重试
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"生成施工单号失败，已重试{max_retries}次: {str(e)}")
                    raise
                logger.warning(f"生成施工单号时发生数据库错误，正在重试 ({retry_count}/{max_retries}): {str(e)}")
                continue
            except Exception as e:
                logger.error(f"生成施工单号时发生未知错误: {str(e)}")
                raise

        # 理论上不会到达这里
        raise Exception("生成施工单号失败：超过最大重试次数")
    
    def save(self, *args, **kwargs):
        """保存时自动生成施工单号"""
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)


class WorkOrderProcess(models.Model):
    """施工单工序记录"""
    STATUS_CHOICES = [
        ('pending', '待开始'),
        ('in_progress', '进行中'),
        ('completed', '已完成'),
        ('skipped', '已跳过'),
    ]

    work_order = models.ForeignKey('WorkOrder', on_delete=models.CASCADE, 
                                   related_name='order_processes', verbose_name='施工单')
    process = models.ForeignKey('workorder.Process', on_delete=models.PROTECT, verbose_name='工序')
    department = models.ForeignKey('workorder.Department', on_delete=models.PROTECT, null=True, blank=True,
                                  verbose_name='生产部门', help_text='指定该工序由哪个部门生产')
    
    sequence = models.IntegerField('工序顺序', default=0)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='operated_processes', verbose_name='操作员')
    
    planned_start_time = models.DateTimeField('计划开始时间', null=True, blank=True)
    planned_end_time = models.DateTimeField('计划结束时间', null=True, blank=True)
    
    actual_start_time = models.DateTimeField('实际开始时间', null=True, blank=True)
    actual_end_time = models.DateTimeField('实际结束时间', null=True, blank=True)
    
    duration_hours = models.DecimalField('耗时(小时)', max_digits=6, decimal_places=2, 
                                        default=0, blank=True)
    
    quantity_completed = models.IntegerField('完成数量', default=0)
    quantity_defective = models.IntegerField('不良品数量', default=0)
    
    notes = models.TextField('备注', blank=True)
    
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '施工单工序'
        verbose_name_plural = '施工单工序管理'
        ordering = ['work_order', 'sequence']
        unique_together = ['work_order', 'sequence']
        # 添加索引以优化查询性能
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['status', 'sequence']),  # 组合索引
            models.Index(fields=['work_order', 'status']),  # 组合索引
            models.Index(fields=['department']),
            models.Index(fields=['operator']),
            models.Index(fields=['planned_start_time']),
            models.Index(fields=['actual_start_time']),
        ]

    def __str__(self):
        return f"{self.work_order.order_number} - {self.process.name}"
    
    def can_start(self):
        """判断该工序是否可以开始"""
        # 如果工序已经开始或完成，不能重新开始
        if self.status in ['in_progress', 'completed', 'cancelled']:
            return False

        # 使用配置字段或编码判断是否可并行
        # 注意：采购不属于施工单工序，采购任务通过其他系统管理
        from .process_codes import ProcessCodes

        # 优先使用配置字段，如果未配置则使用编码判断
        if self.process.is_parallel or ProcessCodes.is_parallel(self.process.code):
            # 这些工序可以并行，只要没有其他限制就可以开始
            return True

        # 其他工序需要前一个工序完成
        # 获取所有非并行工序，按 sequence 排序
        non_parallel_processes = WorkOrderProcess.objects.filter(
            work_order=self.work_order
        ).exclude(
            process__is_parallel=True
        ).exclude(
            process__code__in=[ProcessCodes.CTP, ProcessCodes.DIE]
        ).order_by('sequence')

        # 找到当前工序在非并行工序中的位置
        current_idx = None
        for idx, wp in enumerate(non_parallel_processes):
            if wp.id == self.id:
                current_idx = idx
                break

        # 如果是第一个非并行工序，可以开始
        if current_idx == 0:
            return True

        # 检查前一个非并行工序是否完成
        if current_idx and current_idx > 0:
            previous_process = non_parallel_processes[current_idx - 1]
            return previous_process.status == 'completed'

        return True
    
    def check_and_update_status(self):
        """根据任务状态自动判断工序是否完成（新规则）

        - 不再依赖 task_generation_rule
        - 若无任务，返回 False
        - 所有任务需状态为 completed
        - 若任务有生产数量，需 quantity_completed >= production_quantity
        - 增加业务条件检查：制版任务需图稿确认，开料任务需物料状态满足条件
        - 注意：采购不属于施工单工序，采购任务通过其他系统管理
        """
        tasks = self.tasks.all()
        if not tasks.exists():
            return False

        from .process_codes import ProcessCodes
        
        process_code = self.process.code

        for task in tasks:
            if task.status != 'completed':
                return False
            if task.production_quantity and task.quantity_completed < task.production_quantity:
                return False
            
            # 业务条件检查：制版任务需图稿/刀模等已确认
            if task.task_type == 'plate_making':
                # 检查图稿确认状态
                if task.artwork and not task.artwork.confirmed:
                    return False
                # 检查刀模确认状态
                if task.die and not task.die.confirmed:
                    return False
                # 检查烫金版确认状态
                if task.foiling_plate and not task.foiling_plate.confirmed:
                    return False
                # 检查压凸版确认状态
                if task.embossing_plate and not task.embossing_plate.confirmed:
                    return False
            
            # 业务条件检查：开料任务需物料状态满足条件
            # 注意：只有CUT工序生成cutting类型任务
            # 采购不属于施工单工序，采购任务通过其他系统管理，物料采购状态在WorkOrderMaterial中记录
            if task.task_type == 'cutting' and task.material:
                work_order_material = self.work_order.materials.filter(material=task.material).first()
                if work_order_material:
                    # 使用编码判断：开料工序（CUT）物料必须已开料
                    if ProcessCodes.requires_material_cut_status(process_code):
                        if work_order_material.purchase_status != 'cut':
                            return False

        # 汇总任务的完成数量和不良品数量
        total_quantity_completed = sum(task.quantity_completed or 0 for task in tasks)
        total_quantity_defective = sum(task.quantity_defective or 0 for task in tasks)
        
        # 获取施工单对象
        work_order = self.work_order

        # 更新工序的完成数量和不良品数量（如果工序数量为0，则使用汇总值）
        if not self.quantity_completed:
            self.quantity_completed = total_quantity_completed
        if not self.quantity_defective:
            self.quantity_defective = total_quantity_defective
        
        self.status = 'completed'
        self.actual_end_time = timezone.now()
        self.save()

        # 如果是包装任务，更新产品库存
        if self.process.code == 'PACK':
            self._update_product_stock_on_packaging()

        # 创建工序完成通知
        from .system import Notification
        # 通知施工单创建人
        if work_order.created_by:
            Notification.create_notification(
                recipient=work_order.created_by,
                notification_type='process_completed',
                title=f'工序完成：{self.process.name}',
                content=f'施工单 {work_order.order_number} 的工序"{self.process.name}"已完成',
                priority='normal',
                work_order=work_order,
                work_order_process=self
            )
        
        # 检查是否所有工序都完成，如果是则自动标记施工单为完成
        work_order = self.work_order
        all_processes_completed = work_order.order_processes.exclude(
            status='completed'
        ).count() == 0
        
        if all_processes_completed and work_order.status != 'completed':
            work_order.status = 'completed'
            work_order.save()
            
            # 创建施工单完成通知
            if work_order.created_by:
                Notification.create_notification(
                    recipient=work_order.created_by,
                    notification_type='workorder_completed',
                    title=f'施工单完成：{work_order.order_number}',
                    content=f'施工单 {work_order.order_number} 所有工序已完成，施工单已标记为完成',
                    priority='high',
                    work_order=work_order
                )
        
        return True
    
    def _auto_assign_task(self, task):
        """自动分派任务到部门和操作员
        
        分派规则：
        1. 优先使用工序级别的分派（self.department, self.operator）
        2. 如果工序未指定部门，根据工序与部门的关联关系自动分派：
           - 优先选择专业车间（排除外协车间）
           - 如果部门编码与工序编码匹配（如 die_cutting 对应 DIE），优先选择
           - 如果只有外协车间，则选择外协车间
           - 如果都没有，选择父部门（生产部）
        3. 如果工序未指定操作员，从分派部门中选择第一个操作员（可选）
        """
        # 优先使用工序级别的分派
        if self.department:
            task.assigned_department = self.department
        else:
            # 使用配置的分派规则
            from .system import TaskAssignmentRule
            assignment_rules = TaskAssignmentRule.objects.filter(
                process=self.process,
                is_active=True
            ).select_related('department').order_by('-priority', 'department')
            
            # 获取可用部门列表（工序关联的部门）
            available_departments = Department.objects.filter(
                processes=self.process,
                is_active=True
            )
            
            if assignment_rules.exists():
                # 使用配置的规则，按优先级选择
                # 检查规则中的部门是否在可用部门列表中
                for rule in assignment_rules:
                    if rule.department in available_departments:
                        task.assigned_department = rule.department
                        break
                
                # 如果配置的规则都没有匹配到，选择第一个可用部门作为兜底
                if not task.assigned_department and available_departments.exists():
                    task.assigned_department = available_departments.order_by('sort_order').first()
            else:
                # 如果没有配置规则，选择第一个可用部门作为兜底
                if available_departments.exists():
                    task.assigned_department = available_departments.order_by('sort_order').first()
        
        # 如果工序已指定操作员，使用工序的操作员
        if self.operator:
            task.assigned_operator = self.operator
        elif task.assigned_department:
            # 如果已分派部门但未分派操作员，从部门中选择操作员
            # 优先使用配置规则中的操作员选择策略
            from .system import TaskAssignmentRule
            assignment_rule = TaskAssignmentRule.objects.filter(
                process=self.process,
                department=task.assigned_department,
                is_active=True
            ).order_by('-priority').first()
            
            strategy = 'least_tasks'  # 默认策略
            if assignment_rule:
                strategy = assignment_rule.operator_selection_strategy
            
            task.assigned_operator = self._select_operator_by_strategy(
                task.assigned_department, strategy
            )
        
        task.save()
        
        # 创建任务分派通知
        if task.assigned_operator:
            from .system import Notification
            Notification.create_notification(
                recipient=task.assigned_operator,
                notification_type='task_assigned',
                title=f'新任务分派：{task.work_content}',
                content=f'您有一个新任务：{task.work_content}（施工单：{self.work_order.order_number}）',
                priority='normal',
                work_order=self.work_order,
                work_order_process=self,
                task=task
            )

    def _update_product_stock_on_packaging(self):
        """包装工序完成时，更新产品的库存数量

        优化规则：
        - 使用事务确保库存更新的原子性
        - 批量锁定产品记录，避免并发冲突
        - 避免重复计算已入库的数量
        - 记录详细的库存变更日志
        """
        from django.db import transaction
        from .products import Product
        from .services.data_consistency import StockConsistencyService

        with transaction.atomic():
            # 获取所有未计入库存的包装任务，使用 select_related 优化查询
            packaging_tasks = self.tasks.filter(
                task_type='packaging',
                status='completed'
            ).select_related('product').all()

            # 按产品分组汇总需要入库的数量
            product_quantities = {}
            task_updates = []

            for task in packaging_tasks:
                if not task.product:
                    continue

                product_id = task.product.id
                # 计算实际需要入库的数量
                # 新增数量 = 当前总完成数量 - 上次已计入库存的数量
                actual_quantity_to_stock = task.quantity_completed - (task.stock_accounted_quantity or 0)

                if actual_quantity_to_stock > 0:
                    if product_id not in product_quantities:
                        product_quantities[product_id] = 0
                    product_quantities[product_id] += actual_quantity_to_stock

                    # 准备任务更新
                    task.stock_accounted_quantity = task.quantity_completed
                    task_updates.append(task)

            # 批量更新任务状态
            if task_updates:
                WorkOrderTask.objects.bulk_update(
                    task_updates,
                    ['stock_accounted_quantity']
                )

            # 批量更新产品库存 - 优化：一次性锁定所有需要更新的产品
            stock_updates = []
            if product_quantities:
                # 使用 select_for_update() 批量锁定所有相关产品，避免并发冲突
                products = Product.objects.select_for_update().filter(
                    id__in=product_quantities.keys()
                )

                # 创建产品ID到产品对象的映射
                product_map = {p.id: p for p in products}

                for product_id, quantity in product_quantities.items():
                    if product_id not in product_map:
                        # 产品已被删除，记录日志但继续处理
                        logger.warning(f"产品ID {product_id} 不存在，跳过库存更新")
                        continue

                    product = product_map[product_id]
                    old_quantity = product.stock_quantity
                    new_quantity = old_quantity + quantity
                    product.stock_quantity = new_quantity
                    stock_updates.append((product, old_quantity, new_quantity, quantity))

            # 批量保存产品库存
            if stock_updates:
                products_to_update = [item[0] for item in stock_updates]
                Product.objects.bulk_update(products_to_update, ['stock_quantity'])

                # 创建库存变更日志
                from .products import ProductStockLog
                log_entries = []
                for product, old_quantity, new_quantity, quantity in stock_updates:
                    log_entries.append(ProductStockLog(
                        product=product,
                        change_type='add',
                        quantity=quantity,
                        old_quantity=old_quantity,
                        new_quantity=new_quantity,
                        reason=f'施工单{self.work_order.order_number}包装工序完成，入库{quantity}{product.unit}',
                        created_by=None
                    ))

                ProductStockLog.objects.bulk_create(log_entries)

                # 检查库存预警
                for product, _, new_quantity, _ in stock_updates:
                    if product.is_low_stock():
                        product._send_low_stock_warning()

    def _select_operator_by_strategy(self, department, strategy):
        """根据策略从部门中选择操作员"""
        from django.contrib.auth.models import User
        from django.db.models import Count, Q
        import random
        
        department_users = User.objects.filter(
            profile__departments=department,
            is_active=True
        ).exclude(
            is_superuser=True  # 排除超级管理员
        )
        
        if not department_users.exists():
            return None
        
        if strategy == 'least_tasks':
            # 优先选择任务数量较少的操作员（工作量均衡）
            users_with_task_count = []
            for user in department_users:
                task_count = WorkOrderTask.objects.filter(
                    assigned_operator=user,
                    status__in=['pending', 'in_progress']
                ).count()
                users_with_task_count.append((user, task_count))
            
            # 按任务数量排序，优先选择任务数量最少的操作员
            users_with_task_count.sort(key=lambda x: x[1])
            return users_with_task_count[0][0]
        
        elif strategy == 'random':
            # 随机选择
            return random.choice(list(department_users))
        
        elif strategy == 'round_robin':
            # 轮询分配（简单实现：按ID排序后选择）
            # TODO: 可以实现更复杂的轮询逻辑（记录上次分配的操作员）
            return department_users.order_by('id').first()
        
        elif strategy == 'first_available':
            # 选择第一个可用操作员
            return department_users.first()
        
        else:
            # 默认使用least_tasks策略
            return self._select_operator_by_strategy(department, 'least_tasks')
    
    def generate_tasks(self):
        """为工序生成任务（在工序开始时调用）
        
        使用 process.code 字段精确匹配工序，生成对应的任务：
        - CTP（制版）：为图稿、刀模、烫金版、压凸版每个生成一个任务
        - CUT（开料）：为需要开料的物料每个生成一个任务
        - PRT（印刷）：为每个图稿生成一个任务
        - FOIL_G（烫金）：为每个烫金版生成一个任务
        - EMB（压凸）：为每个压凸版生成一个任务
        - DIE（模切）：为每个刀模生成一个任务
        - PACK（包装）：为每个产品生成一个任务
        - 其他工序：生成通用任务
        """
        from .process_codes import ProcessCodes
        
        # 如果已经有任务，不再生成
        if self.tasks.exists():
            return
        
        process = self.process
        work_order = self.work_order
        process_code = process.code
        order_number = work_order.order_number
        production_quantity = work_order.production_quantity or 0
        
        # 使用 code 字段精确匹配工序
        if process_code == ProcessCodes.CTP:
            # 制版工序：为图稿、刀模、烫金版、压凸版每个生成一个任务
            # 任务内容：{施工单号}制版审核，生产数量：1
            # 图稿任务
            for artwork in work_order.artworks.all():
                task = WorkOrderTask.objects.create(
                    work_order_process=self,
                    task_type='plate_making',
                    artwork=artwork,
                    work_content=f'{order_number}制版审核',
                    production_quantity=1,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=True  # 启用自动计算：图稿确认后自动更新
                )
                self._auto_assign_task(task)
            # 刀模任务
            for die in work_order.dies.all():
                task = WorkOrderTask.objects.create(
                    work_order_process=self,
                    task_type='plate_making',
                    die=die,
                    work_content=f'{order_number}制版审核',
                    production_quantity=1,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=True  # 启用自动计算：刀模确认后自动更新
                )
                self._auto_assign_task(task)
            # 烫金版任务
            for foiling_plate in work_order.foiling_plates.all():
                task = WorkOrderTask.objects.create(
                    work_order_process=self,
                    task_type='plate_making',
                    foiling_plate=foiling_plate,
                    work_content=f'{order_number}制版审核',
                    production_quantity=1,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=True  # 启用自动计算：烫金版确认后自动更新
                )
                self._auto_assign_task(task)
            # 压凸版任务
            for embossing_plate in work_order.embossing_plates.all():
                task = WorkOrderTask.objects.create(
                    work_order_process=self,
                    task_type='plate_making',
                    embossing_plate=embossing_plate,
                    work_content=f'{order_number}制版审核',
                    production_quantity=1,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=True  # 启用自动计算：压凸版确认后自动更新
                )
                self._auto_assign_task(task)
        
        elif process_code == ProcessCodes.CUT:
            # 开料工序：为需要开料的物料每个生成一个任务
            # 任务内容：{施工单号}开料，生产数量：物料用量
            for material_item in work_order.materials.all():
                if material_item.need_cutting:
                    quantity = self._parse_material_usage(material_item.material_usage)
                    task = WorkOrderTask.objects.create(
                        work_order_process=self,
                        task_type='cutting',
                        material=material_item.material,
                        work_content=f'{order_number}开料',
                        production_quantity=quantity,
                        quantity_completed=0,
                        status='pending',
                        auto_calculate_quantity=True  # 开料任务启用自动计算
                    )
                    self._auto_assign_task(task)
        
        elif process_code == ProcessCodes.PRT:
            # 印刷工序：为每个图稿生成一个任务
            # 任务内容：{施工单号}印刷，生产数量：施工单的生产数量
            for artwork in work_order.artworks.all():
                task = WorkOrderTask.objects.create(
                    work_order_process=self,
                    task_type='printing',
                    artwork=artwork,
                    work_content=f'{order_number}印刷',
                    production_quantity=production_quantity,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=False
                )
                self._auto_assign_task(task)
        
        elif process_code == ProcessCodes.FOIL_G:
            # 烫金工序：为每个烫金版生成一个任务（参考印刷任务）
            # 任务内容：{施工单号}烫金，生产数量：施工单的生产数量
            for foiling_plate in work_order.foiling_plates.all():
                task = WorkOrderTask.objects.create(
                    work_order_process=self,
                    task_type='foiling',
                    foiling_plate=foiling_plate,
                    work_content=f'{order_number}烫金',
                    production_quantity=production_quantity,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=False
                )
                self._auto_assign_task(task)
        
        elif process_code == ProcessCodes.EMB:
            # 压凸工序：为每个压凸版生成一个任务（参考印刷任务）
            # 任务内容：{施工单号}压凸，生产数量：施工单的生产数量
            for embossing_plate in work_order.embossing_plates.all():
                task = WorkOrderTask.objects.create(
                    work_order_process=self,
                    task_type='embossing',
                    embossing_plate=embossing_plate,
                    work_content=f'{order_number}压凸',
                    production_quantity=production_quantity,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=False
                )
                self._auto_assign_task(task)
        
        elif process_code == ProcessCodes.DIE:
            # 模切工序：为每个刀模生成一个任务（参考印刷任务）
            # 任务内容：{施工单号}模切，生产数量：施工单的生产数量
            for die in work_order.dies.all():
                task = WorkOrderTask.objects.create(
                    work_order_process=self,
                    task_type='die_cutting',
                    die=die,
                    work_content=f'{order_number}模切',
                    production_quantity=production_quantity,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=False
                )
                self._auto_assign_task(task)
        
        elif process_code == ProcessCodes.PACK:
            # 包装工序：为每个产品生成一个任务
            # 任务内容：{产品名称}包装，生产数量：产品数量
            for product_item in work_order.products.all():
                task = WorkOrderTask.objects.create(
                    work_order_process=self,
                    task_type='packaging',
                    product=product_item.product,
                    work_content=f'{product_item.product.name}包装',
                    production_quantity=product_item.quantity,
                    quantity_completed=0,
                    status='pending',
                    auto_calculate_quantity=False
                )
                self._auto_assign_task(task)
        
        else:
            # 其他工序：生成通用任务
            # 任务内容：{工序名称}：{施工单号}，生产数量：施工单的生产数量
            task = WorkOrderTask.objects.create(
                work_order_process=self,
                task_type='general',
                work_content=f'{process.name}：{order_number}',
                production_quantity=production_quantity,
                quantity_completed=0,
                status='pending',
                auto_calculate_quantity=False
            )
            self._auto_assign_task(task)
    
    def _parse_material_usage(self, usage_str):
        """解析物料用量字符串，提取数字部分"""
        if not usage_str:
            return 0
        
        import re
        # 尝试提取数字（支持整数和小数）
        numbers = re.findall(r'\d+\.?\d*', usage_str)
        if numbers:
            try:
                return int(float(numbers[0]))
            except (ValueError, IndexError):
                return 0
        return 0

    def calculate_duration(self):
        """计算工序耗时"""
        if self.actual_start_time and self.actual_end_time:
            duration = self.actual_end_time - self.actual_start_time
            self.duration_hours = round(duration.total_seconds() / 3600, 2)
            self.save(update_fields=['duration_hours'])


class WorkOrderProduct(models.Model):
    """施工单产品关联（支持一个施工单包含多个产品，如一套图稿中拼版了多个产品）"""
    work_order = models.ForeignKey('WorkOrder', on_delete=models.CASCADE,
                                   related_name='products', verbose_name='施工单')
    product = models.ForeignKey('workorder.Product', on_delete=models.PROTECT, verbose_name='产品')
    quantity = models.IntegerField('数量', default=1)
    unit = models.CharField('单位', max_length=20, default='件')
    specification = models.TextField('产品规格', blank=True)
    sort_order = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '施工单产品'
        verbose_name_plural = '施工单产品管理'
        ordering = ['work_order', 'sort_order']
        unique_together = ['work_order', 'product', 'sort_order']

    def __str__(self):
        return f"{self.work_order.order_number} - {self.product.name} ({self.quantity}{self.unit})"


class WorkOrderMaterial(models.Model):
    """施工单物料使用记录"""
    PURCHASE_STATUS_CHOICES = [
        ('pending', '待采购'),
        ('ordered', '已下单'),
        ('received', '已回料'),
        ('cut', '已开料'),
        ('completed', '已完成'),
    ]
    
    work_order = models.ForeignKey('WorkOrder', on_delete=models.CASCADE,
                                   related_name='materials', verbose_name='施工单')
    material = models.ForeignKey('workorder.Material', on_delete=models.PROTECT, verbose_name='物料')
    
    material_size = models.CharField('尺寸', max_length=100, blank=True, help_text='如：A4、210x297mm等')
    material_usage = models.CharField('用量', max_length=100, blank=True, help_text='如：1000张、50平方米等')
    
    # 开料相关
    need_cutting = models.BooleanField('需要开料', default=False, 
                                      help_text='该物料是否需要开料工序处理')
    
    # 采购和开料状态
    purchase_status = models.CharField('采购状态', max_length=20, choices=PURCHASE_STATUS_CHOICES,
                                      default='pending', help_text='物料的采购和开料状态')
    purchase_date = models.DateField('采购日期', null=True, blank=True, help_text='采购下单日期')
    received_date = models.DateField('回料日期', null=True, blank=True, help_text='物料回料日期')
    cut_date = models.DateField('开料日期', null=True, blank=True, help_text='切料组开料日期')
    
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '施工单物料'
        verbose_name_plural = '施工单物料管理'
        ordering = ['work_order', 'material']

    def __str__(self):
        return f"{self.work_order.order_number} - {self.material.name}"


class ProcessLog(models.Model):
    """工序日志"""
    LOG_TYPE_CHOICES = [
        ('start', '开始'),
        ('pause', '暂停'),
        ('resume', '恢复'),
        ('complete', '完成'),
        ('note', '备注'),
    ]

    work_order_process = models.ForeignKey('WorkOrderProcess', on_delete=models.CASCADE,
                                          related_name='logs', verbose_name='工序')
    log_type = models.CharField('日志类型', max_length=20, choices=LOG_TYPE_CHOICES)
    content = models.TextField('内容')
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='操作员')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '工序日志'
        verbose_name_plural = '工序日志'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.work_order_process} - {self.get_log_type_display()}"


class TaskLog(models.Model):
    """任务操作日志"""
    LOG_TYPE_CHOICES = [
        ('update_quantity', '更新数量'),
        ('complete', '强制完成'),
        ('status_change', '状态变更'),
    ]

    task = models.ForeignKey('WorkOrderTask', on_delete=models.CASCADE,
                             related_name='logs', verbose_name='任务')
    log_type = models.CharField('日志类型', max_length=20, choices=LOG_TYPE_CHOICES)
    content = models.TextField('内容', help_text='操作内容描述')
    quantity_before = models.IntegerField('更新前数量', null=True, blank=True)
    quantity_after = models.IntegerField('更新后数量', null=True, blank=True)
    quantity_increment = models.IntegerField('数量增量', null=True, blank=True, help_text='本次操作的数量增量')
    quantity_defective_increment = models.IntegerField('不良品数量增量', null=True, blank=True, 
                                                       help_text='本次操作的不良品数量增量')
    status_before = models.CharField('更新前状态', max_length=20, null=True, blank=True)
    status_after = models.CharField('更新后状态', max_length=20, null=True, blank=True)
    completion_reason = models.TextField('完成理由', blank=True, help_text='强制完成时的理由说明')
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='操作员')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '任务操作日志'
        verbose_name_plural = '任务操作日志'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.task} - {self.get_log_type_display()}"


class WorkOrderTask(models.Model):
    """施工单任务（为工序生成的具体任务）"""
    TASK_TYPE_CHOICES = [
        ('plate_making', '制版任务'),
        ('cutting', '开料任务'),
        ('printing', '印刷任务'),
        ('foiling', '烫金任务'),
        ('embossing', '压凸任务'),
        ('die_cutting', '模切任务'),
        ('packaging', '包装任务'),
        ('general', '通用任务'),
    ]
    
    work_order_process = models.ForeignKey('WorkOrderProcess', on_delete=models.CASCADE,
                                          related_name='tasks', verbose_name='工序')
    task_type = models.CharField('任务类型', max_length=20, choices=TASK_TYPE_CHOICES,
                                default='general', help_text='任务类型，用于区分不同的任务生成规则')
    work_content = models.TextField('施工内容', help_text='具体的施工内容描述')
    production_quantity = models.IntegerField('生产数量', default=0, help_text='该任务需要生产的数量')
    quantity_completed = models.IntegerField('完成数量', default=0, 
                                           help_text='任务完成数量，可自动计算或手动输入')
    quantity_defective = models.IntegerField('不良品数量', default=0,
                                           help_text='任务不良品数量，在任务完成时记录')
    auto_calculate_quantity = models.BooleanField('自动计算数量', default=True,
                                                  help_text='是否自动计算完成数量')
    # 关联对象（根据任务类型，只有一个字段会有值）
    artwork = models.ForeignKey('workorder.Artwork', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='tasks', verbose_name='关联图稿')
    die = models.ForeignKey('workorder.Die', on_delete=models.CASCADE, null=True, blank=True,
                           related_name='tasks', verbose_name='关联刀模')
    product = models.ForeignKey('workorder.Product', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='tasks', verbose_name='关联产品')
    material = models.ForeignKey('workorder.Material', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='tasks', verbose_name='关联物料')
    foiling_plate = models.ForeignKey('workorder.FoilingPlate', on_delete=models.CASCADE, null=True, blank=True,
                                     related_name='tasks', verbose_name='关联烫金版')
    embossing_plate = models.ForeignKey('workorder.EmbossingPlate', on_delete=models.CASCADE, null=True, blank=True,
                                       related_name='tasks', verbose_name='关联压凸版')
    production_requirements = models.TextField('生产要求', blank=True, help_text='生产过程中的特殊要求')
    stock_accounted_quantity = models.IntegerField('已计入库存的完成数量', default=0, 
                                              help_text='该任务已计入产品库存的完成数量，用于编辑数量时计算差异')
    # 任务分派（任务级别的分派，支持精细化管理）
    assigned_department = models.ForeignKey('workorder.Department', on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='assigned_tasks', verbose_name='分派部门',
                                           help_text='该任务分派给哪个部门执行')
    assigned_operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='assigned_tasks', verbose_name='分派操作员',
                                         help_text='该任务分派给哪个操作员执行')
    # 任务拆分支持（多人协作）
    parent_task = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                                    related_name='subtasks', verbose_name='父任务',
                                    help_text='如果该任务是子任务，指向父任务')
    # 并发控制（乐观锁）
    version = models.IntegerField('版本号', default=1, help_text='用于乐观锁，防止并发更新冲突')
    status = models.CharField('状态', max_length=20,
                             choices=[('draft', '草稿'), ('pending', '待开始'), ('in_progress', '进行中'),
                                     ('completed', '已完成'), ('cancelled', '已取消')],
                             default='pending')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '施工单任务'
        verbose_name_plural = '施工单任务管理'
        ordering = ['work_order_process', 'created_at']
        # 添加索引以优化查询性能
        indexes = [
            models.Index(fields=['assigned_department']),
            models.Index(fields=['assigned_operator']),
            models.Index(fields=['status']),
            models.Index(fields=['assigned_department', 'status']),  # 组合索引
            models.Index(fields=['work_order_process', 'status']),  # 组合索引
            models.Index(fields=['task_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        return f"{self.work_order_process} - {self.work_content[:50]}"
    
    def is_subtask(self):
        """判断是否为子任务"""
        return self.parent_task is not None
    
    def get_subtasks(self):
        """获取所有子任务"""
        return self.subtasks.all()
    
    def update_from_subtasks(self):
        """从子任务汇总数量和状态到父任务"""
        if not self.is_subtask() and self.subtasks.exists():
            subtasks = self.subtasks.all()
            # 汇总完成数量
            total_completed = sum(st.quantity_completed or 0 for st in subtasks)
            # 汇总不良品数量
            total_defective = sum(st.quantity_defective or 0 for st in subtasks)
            
            # 更新父任务
            self.quantity_completed = total_completed
            self.quantity_defective = total_defective
            
            # 判断父任务状态：所有子任务完成则父任务完成
            all_subtasks_completed = subtasks.exclude(status='completed').count() == 0
            if all_subtasks_completed and self.status != 'completed':
                self.status = 'completed'
            elif not all_subtasks_completed and self.status == 'completed':
                self.status = 'in_progress'

            self.save(update_fields=['quantity_completed', 'quantity_defective', 'status', 'updated_at'])
            return True
        return False

    def update_quantity(self, increment, user=None):
        """
        增量更新完成数量

        Args:
            increment: 增量值（可以是正数或负数）
            user: 更新的用户（可选）

        Returns:
            bool: 更新是否成功
        """
        from django.utils import timezone

        # 保存旧值
        old_quantity = self.quantity_completed

        # 更新数量
        self.quantity_completed += increment

        # 确保不超过生产数量
        if self.quantity_completed > self.production_quantity:
            self.quantity_completed = self.production_quantity

        # 确保不为负数
        if self.quantity_completed < 0:
            self.quantity_completed = 0

        # 如果达到生产数量，自动完成任务
        if self.quantity_completed >= self.production_quantity:
            self.status = 'completed'

        # 保存（会自动递增版本号）
        self.save()

        # 创建任务日志
        TaskLog.objects.create(
            task=self,
            log_type='update_quantity',
            operator=user,
            content=f'数量从 {old_quantity} 更新到 {self.quantity_completed}',
            quantity_before=old_quantity,
            quantity_after=self.quantity_completed,
            quantity_increment=increment
        )

        return True

    def save(self, *args, **kwargs):
        """保存时实现乐观锁机制

        优化：使用 update() 方法实现乐观锁，避免行锁，提升并发性能
        """
        # 如果是更新操作，使用乐观锁检查版本号
        if self.pk:
            # 使用 update() 方法实现乐观锁，避免 select_for_update 行锁
            # 这种方式只在版本号匹配时更新，返回更新的行数
            updated = WorkOrderTask.objects.filter(
                pk=self.pk,
                version=self.version
            ).exclude(
                # 排除当前对象本身（如果它已经在内存中）
            ).update(version=self.version + 1)

            if updated == 0:
                # 版本号不匹配，说明数据已被其他用户修改
                # 或者是第一次保存（版本号还是默认值）
                # 需要从数据库获取当前版本号进行验证
                try:
                    current = WorkOrderTask.objects.get(pk=self.pk)
                    if current.version != self.version:
                        from workorder.exceptions import BusinessLogicError
                        raise BusinessLogicError(
                            f"数据已被其他用户修改，请刷新后重试。"
                            f"当前版本: {current.version}, 您的版本: {self.version}"
                        )
                    # 版本号相同但 updated 为 0，说明是第一次保存
                    # 继续执行保存操作
                except WorkOrderTask.DoesNotExist:
                    # 记录不存在，可能是被删除了
                    from workorder.exceptions import BusinessLogicError
                    raise BusinessLogicError("该任务已被删除，请刷新页面")

            # 更新成功，递增版本号
            self.version += 1

        super().save(*args, **kwargs)


