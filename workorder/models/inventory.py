"""
库存相关模型

包含库存管理的相关模型：
- ProductStock: 成品库存
- StockIn: 入库单
- StockOut: 出库单
- DeliveryOrder: 发货单
- DeliveryItem: 发货明细
- QualityInspection: 质量检验
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction


class ProductStock(models.Model):
    """成品库存"""
    product = models.ForeignKey('workorder.Product', on_delete=models.CASCADE, verbose_name='产品')
    quantity = models.DecimalField('库存数量', max_digits=10, decimal_places=2, default=0)
    reserved_quantity = models.DecimalField('预留数量', max_digits=10, decimal_places=2, default=0)
    min_stock_level = models.DecimalField('最小库存', max_digits=10, decimal_places=2, default=0,
                                          help_text='库存低于此数量时触发预警')
    unit_cost = models.DecimalField('单位成本', max_digits=10, decimal_places=2, default=0)
    location = models.CharField('库位', max_length=50, blank=True, help_text='如: A01-01-01')
    batch_no = models.CharField('批次号', max_length=50, unique=True)
    work_order = models.ForeignKey('workorder.WorkOrder', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='product_stocks', verbose_name='来源施工单')

    # 质量信息
    production_date = models.DateField('生产日期', null=True, blank=True)
    expiry_date = models.DateField('有效期', null=True, blank=True)

    # 状态
    STATUS_CHOICES = [
        ('in_stock', '在库'),
        ('reserved', '已预留'),
        ('quality_check', '质检中'),
        ('defective', '次品'),
    ]
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='in_stock')

    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    @property
    def available_quantity(self):
        """可用数量 = 库存数量 - 预留数量"""
        return self.quantity - self.reserved_quantity

    @property
    def total_value(self):
        """总价值 = 库存数量 * 单位成本"""
        return self.quantity * self.unit_cost

    @property
    def is_low_stock(self):
        """是否低库存"""
        return self.available_quantity <= self.min_stock_level

    class Meta:
        verbose_name = '成品库存'
        verbose_name_plural = '成品库存管理'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['batch_no']),
            models.Index(fields=['status']),
            models.Index(fields=['location']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.batch_no}"

    def is_expired(self):
        """检查是否过期"""
        if self.expiry_date:
            return timezone.now().date() > self.expiry_date
        return False

    def reserve(self, quantity):
        """预留库存"""
        if self.quantity >= quantity:
            self.quantity -= quantity
            self.status = 'reserved'
            self.save()
            return True
        return False


class StockIn(models.Model):
    """入库单"""
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('submitted', '已提交'),
        ('approved', '已审核'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]

    @staticmethod
    def generate_order_number():
        """生成入库单号：RK + yyyymmdd + 4位序号"""
        today = timezone.now().strftime('%Y%m%d')
        prefix = f'RK{today}'
        with transaction.atomic():
            latest = StockIn.objects.filter(
                order_number__startswith=prefix
            ).select_for_update().order_by('-order_number').first()
            if latest:
                last_number = int(latest.order_number[-4:])
                new_number = last_number + 1
            else:
                new_number = 1
            return f'{prefix}{new_number:04d}'

    order_number = models.CharField('入库单号', max_length=50, unique=True, editable=False)
    work_order = models.ForeignKey('workorder.WorkOrder', on_delete=models.CASCADE,
                                  related_name='stock_ins', verbose_name='施工单')
    stock_in_date = models.DateField('入库日期', default=timezone.now)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='draft')

    # 审核信息
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='submitted_stock_ins', verbose_name='提交人')
    submitted_at = models.DateTimeField('提交时间', null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='approved_stock_ins', verbose_name='审核人')
    approved_at = models.DateTimeField('审核时间', null=True, blank=True)

    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='operated_stock_ins', verbose_name='操作员')
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '入库单'
        verbose_name_plural = '入库单管理'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_number} - {self.work_order.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)


class StockOut(models.Model):
    """出库单"""
    TYPE_CHOICES = [
        ('delivery', '发货出库'),
        ('return', '退货出库'),
        ('transfer', '调拨出库'),
        ('defective', '次品出库'),
    ]

    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('submitted', '已提交'),
        ('approved', '已审核'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]

    @staticmethod
    def generate_order_number():
        """生成出库单号：CK + yyyymmdd + 4位序号"""
        today = timezone.now().strftime('%Y%m%d')
        prefix = f'CK{today}'
        with transaction.atomic():
            latest = StockOut.objects.filter(
                order_number__startswith=prefix
            ).select_for_update().order_by('-order_number').first()
            if latest:
                last_number = int(latest.order_number[-4:])
                new_number = last_number + 1
            else:
                new_number = 1
            return f'{prefix}{new_number:04d}'

    order_number = models.CharField('出库单号', max_length=50, unique=True, editable=False)
    out_type = models.CharField('出库类型', max_length=20, choices=TYPE_CHOICES, default='delivery')
    delivery_order = models.ForeignKey('DeliveryOrder', on_delete=models.CASCADE,
                                     null=True, blank=True, related_name='stock_outs',
                                     verbose_name='发货单')
    stock_out_date = models.DateField('出库日期', default=timezone.now)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='draft')

    # 审核信息
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='submitted_stock_outs', verbose_name='提交人')
    submitted_at = models.DateTimeField('提交时间', null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='approved_stock_outs', verbose_name='审核人')
    approved_at = models.DateTimeField('审核时间', null=True, blank=True)

    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='operated_stock_outs', verbose_name='操作员')
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '出库单'
        verbose_name_plural = '出库单管理'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_number} - {self.get_out_type_display()}"


class DeliveryOrder(models.Model):
    """发货单"""
    STATUS_CHOICES = [
        ('pending', '待发货'),
        ('shipped', '已发货'),
        ('in_transit', '运输中'),
        ('received', '已签收'),
        ('rejected', '拒收'),
        ('returned', '已退货'),
    ]

    @staticmethod
    def generate_order_number():
        """生成发货单号：FH + yyyymmdd + 4位序号"""
        today = timezone.now().strftime('%Y%m%d')
        prefix = f'FH{today}'
        with transaction.atomic():
            latest = DeliveryOrder.objects.filter(
                order_number__startswith=prefix
            ).select_for_update().order_by('-order_number').first()
            if latest:
                last_number = int(latest.order_number[-4:])
                new_number = last_number + 1
            else:
                new_number = 1
            return f'{prefix}{new_number:04d}'

    order_number = models.CharField('发货单号', max_length=50, unique=True, editable=False)
    sales_order = models.ForeignKey('workorder.SalesOrder', on_delete=models.CASCADE,
                                   related_name='delivery_orders', verbose_name='销售订单')
    customer = models.ForeignKey('workorder.Customer', on_delete=models.PROTECT, verbose_name='客户')
    delivery_date = models.DateField('发货日期', null=True, blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')

    # 收货信息
    receiver_name = models.CharField('收货人', max_length=100)
    receiver_phone = models.CharField('联系电话', max_length=50)
    delivery_address = models.TextField('送货地址')

    # 物流信息
    logistics_company = models.CharField('物流公司', max_length=100, blank=True)
    tracking_number = models.CharField('物流单号', max_length=100, blank=True)
    freight = models.DecimalField('运费', max_digits=10, decimal_places=2, default=0)

    # 签收信息
    received_date = models.DateTimeField('签收时间', null=True, blank=True)
    receiver_signature = models.ImageField('签收照片', upload_to='signatures/', null=True, blank=True)
    received_notes = models.TextField('签收备注', blank=True)

    # 包装信息
    package_count = models.IntegerField('包裹数量', default=1)
    package_weight = models.DecimalField('总重量(kg)', max_digits=10, decimal_places=2, null=True, blank=True)

    notes = models.TextField('备注', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_delivery_orders', verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '发货单'
        verbose_name_plural = '发货单管理'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['customer']),
            models.Index(fields=['delivery_date']),
        ]

    def __str__(self):
        return f"{self.order_number} - {self.customer.name}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)


class DeliveryItem(models.Model):
    """发货明细"""
    delivery_order = models.ForeignKey(DeliveryOrder, on_delete=models.CASCADE,
                                     related_name='items', verbose_name='发货单')
    product = models.ForeignKey('workorder.Product', on_delete=models.PROTECT, verbose_name='产品')
    sales_order_item = models.ForeignKey('workorder.SalesOrderItem', on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='delivery_items',
                                         verbose_name='销售订单明细')
    quantity = models.DecimalField('发货数量', max_digits=10, decimal_places=2)
    unit = models.CharField('单位', max_length=20, default='件')
    unit_price = models.DecimalField('单价', max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField('小计', max_digits=12, decimal_places=2, default=0)

    # 关联库存批次
    stock_batch = models.CharField('库存批次号', max_length=50, blank=True)

    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '发货明细'
        verbose_name_plural = '发货明细管理'
        ordering = ['delivery_order', 'id']

    def __str__(self):
        return f"{self.delivery_order.order_number} - {self.product.name}"

    def save(self, *args, **kwargs):
        # 自动计算小计
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class QualityInspection(models.Model):
    """质量检验"""
    TYPE_CHOICES = [
        ('incoming', '来料检验'),
        ('process', '过程检验'),
        ('final', '成品检验'),
        ('customer', '客诉检验'),
    ]

    RESULT_CHOICES = [
        ('pending', '待检验'),
        ('passed', '合格'),
        ('failed', '不合格'),
        ('conditional', '条件接收'),
    ]

    @staticmethod
    def generate_inspection_number():
        """生成质检单号：ZJ + yyyymmdd + 4位序号"""
        today = timezone.now().strftime('%Y%m%d')
        prefix = f'ZJ{today}'
        with transaction.atomic():
            latest = QualityInspection.objects.filter(
                inspection_number__startswith=prefix
            ).select_for_update().order_by('-inspection_number').first()
            if latest:
                last_number = int(latest.inspection_number[-4:])
                new_number = last_number + 1
            else:
                new_number = 1
            return f'{prefix}{new_number:04d}'

    inspection_number = models.CharField('质检单号', max_length=50, unique=True, editable=False)
    inspection_type = models.CharField('检验类型', max_length=20, choices=TYPE_CHOICES)
    work_order = models.ForeignKey('workorder.WorkOrder', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='quality_inspections', verbose_name='施工单')
    product = models.ForeignKey('workorder.Product', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='quality_inspections', verbose_name='产品')
    batch_no = models.CharField('批次号', max_length=50, blank=True)

    # 检验信息
    inspection_date = models.DateField('检验日期', default=timezone.now)
    inspector = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='inspections', verbose_name='质检员')
    result = models.CharField('检验结果', max_length=20, choices=RESULT_CHOICES, default='pending')

    # 数量信息
    inspection_quantity = models.IntegerField('检验数量', default=0)
    passed_quantity = models.IntegerField('合格数量', default=0)
    failed_quantity = models.IntegerField('不合格数量', default=0)
    defective_rate = models.DecimalField('不良率', max_digits=5, decimal_places=2, default=0)

    # 检验标准和项目
    inspection_standard = models.TextField('检验标准', blank=True)
    inspection_items = models.JSONField('检验项目', default=list, blank=True)

    # 缺陷记录
    defects = models.JSONField('缺陷记录', default=list, blank=True)
    defect_description = models.TextField('缺陷描述', blank=True)

    # 处理意见
    disposition = models.CharField('处理意见', max_length=20, blank=True,
                                 choices=[('accept', '接收'), ('rework', '返工'),
                                         ('scrap', '报废'), ('return', '退货')])
    disposition_notes = models.TextField('处理说明', blank=True)

    # 附件
    attachment = models.FileField('检验报告', upload_to='quality_reports/', null=True, blank=True)

    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '质量检验'
        verbose_name_plural = '质量检验管理'
        ordering = ['-inspection_date']
        indexes = [
            models.Index(fields=['inspection_type']),
            models.Index(fields=['result']),
            models.Index(fields=['inspection_date']),
        ]

    def __str__(self):
        return f"{self.inspection_number} - {self.get_inspection_type_display()}"

    def save(self, *args, **kwargs):
        if not self.inspection_number:
            self.inspection_number = self.generate_inspection_number()

        # 计算不良率
        if self.inspection_quantity > 0:
            self.defective_rate = (self.failed_quantity / self.inspection_quantity) * 100

        super().save(*args, **kwargs)
