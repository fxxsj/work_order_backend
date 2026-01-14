"""
物料相关模型

包含物料管理的相关模型：
- Material: 物料信息
- Supplier: 供应商信息
- MaterialSupplier: 物料供应商关联
- PurchaseOrder: 采购单
- PurchaseOrderItem: 采购单明细
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction


class Material(models.Model):
    """物料信息"""
    name = models.CharField('物料名称', max_length=200)
    code = models.CharField('物料编码', max_length=50, unique=True)
    specification = models.CharField('规格', max_length=200, blank=True)
    unit = models.CharField('单位', max_length=20, default='个')
    unit_price = models.DecimalField('单价', max_digits=10, decimal_places=2, default=0)
    stock_quantity = models.DecimalField('库存数量', max_digits=10, decimal_places=2, default=0)
    # 库存预警设置
    min_stock_quantity = models.DecimalField('最小库存', max_digits=10, decimal_places=2, default=0,
                                             help_text='库存低于此数量时触发预警')
    # 采购相关
    default_supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='default_materials', verbose_name='默认供应商',
                                         help_text='该物料的默认供应商')
    lead_time_days = models.IntegerField('采购周期（天）', default=7,
                                       help_text='从下单到收货的天数')
    need_cutting = models.BooleanField('需要开料', default=False,
                                      help_text='该物料是否需要开料工序处理')
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '物料'
        verbose_name_plural = '物料管理'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def is_low_stock(self):
        """检查库存是否不足"""
        return self.stock_quantity < self.min_stock_quantity

    def get_needed_quantity(self, required_quantity):
        """获取需要采购的数量"""
        available = max(0, self.stock_quantity)
        return max(0, required_quantity - available)


class Supplier(models.Model):
    """供应商信息"""
    STATUS_CHOICES = [
        ('active', '启用'),
        ('inactive', '停用'),
    ]

    name = models.CharField('供应商名称', max_length=200)
    code = models.CharField('供应商编码', max_length=50, unique=True)
    contact_person = models.CharField('联系人', max_length=100, blank=True)
    phone = models.CharField('联系电话', max_length=50, blank=True)
    email = models.EmailField('邮箱', blank=True)
    address = models.TextField('地址', blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '供应商'
        verbose_name_plural = '供应商管理'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class MaterialSupplier(models.Model):
    """物料供应商关联（物料可以从多个供应商采购）"""
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name='物料')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name='供应商')
    # 供应商提供的物料信息
    supplier_code = models.CharField('供应商物料编码', max_length=100, blank=True,
                                    help_text='供应商提供的物料编码')
    supplier_price = models.DecimalField('供应商价格', max_digits=10, decimal_places=2,
                                        help_text='该供应商提供的单价')
    is_preferred = models.BooleanField('首选供应商', default=False,
                                      help_text='是否为该物料的首选供应商')
    min_order_quantity = models.DecimalField('最小起订量', max_digits=10, decimal_places=2, default=1,
                                           help_text='该供应商的最小起订量')
    lead_time_days = models.IntegerField('采购周期（天）', default=7,
                                       help_text='该供应商的采购周期')
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '物料供应商关联'
        verbose_name_plural = '物料供应商关联管理'
        ordering = ['material', 'supplier']
        unique_together = ['material', 'supplier']

    def __str__(self):
        return f"{self.material.name} - {self.supplier.name}"


class PurchaseOrder(models.Model):
    """采购单"""
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('submitted', '已提交'),
        ('approved', '已批准'),
        ('ordered', '已下单'),
        ('received', '已收货'),
        ('cancelled', '已取消'),
    ]

    def generate_order_number():
        """生成采购单号：PO + yyyymmdd + 4位序号"""
        today = timezone.now().strftime('%Y%m%d')
        prefix = f'PO{today}'
        with transaction.atomic():
            latest = PurchaseOrder.objects.filter(
                order_number__startswith=prefix
            ).select_for_update().order_by('-order_number').first()
            if latest:
                last_number = int(latest.order_number[-4:])
                new_number = last_number + 1
            else:
                new_number = 1
            return f'{prefix}{new_number:04d}'

    order_number = models.CharField('采购单号', max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name='供应商')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='draft')
    # 合计金额
    total_amount = models.DecimalField('总金额', max_digits=12, decimal_places=2, default=0)
    # 审核相关
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='submitted_purchase_orders', verbose_name='提交人')
    submitted_at = models.DateTimeField('提交时间', null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='approved_purchase_orders', verbose_name='审核人')
    approved_at = models.DateTimeField('审核时间', null=True, blank=True)
    # 采购相关
    ordered_date = models.DateField('下单日期', null=True, blank=True)
    expected_date = models.DateField('预计到货日期', null=True, blank=True,
                                    help_text='供应商预计的到货日期')
    actual_received_date = models.DateField('实际到货日期', null=True, blank=True)
    # 关联信息
    work_order = models.ForeignKey('workorder.WorkOrder', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='purchase_orders', verbose_name='关联施工单',
                                    help_text='如果是为了某个施工单采购，可关联该施工单')
    notes = models.TextField('备注', blank=True)
    rejection_reason = models.TextField('拒绝原因', blank=True,
                                       help_text='如果采购单被拒绝，填写拒绝原因')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '采购单'
        verbose_name_plural = '采购单管理'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_number} - {self.supplier.name}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)

    def update_total_amount(self):
        """更新采购单总金额"""
        total = self.items.aggregate(
            total=models.Sum(models.F('quantity') * models.F('unit_price'))
        )['total'] or 0
        self.total_amount = total
        self.save(update_fields=['total_amount'])


class PurchaseOrderItem(models.Model):
    """采购单明细"""
    STATUS_CHOICES = [
        ('pending', '待收货'),
        ('partial', '部分收货'),
        ('received', '已收货'),
    ]

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE,
                                      related_name='items', verbose_name='采购单')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, verbose_name='物料')
    quantity = models.DecimalField('采购数量', max_digits=10, decimal_places=2)
    received_quantity = models.DecimalField('已收货数量', max_digits=10, decimal_places=2, default=0)
    unit_price = models.DecimalField('单价', max_digits=10, decimal_places=2)
    # 供应商提供的信息
    supplier_code = models.CharField('供应商物料编码', max_length=100, blank=True)
    # 收货状态
    status = models.CharField('收货状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    # 关联施工单物料
    work_order_material = models.ForeignKey('workorder.WorkOrderMaterial', on_delete=models.SET_NULL,
                                           null=True, blank=True, verbose_name='关联施工单物料',
                                           help_text='如果是为了某个施工单采购的物料，可关联')
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '采购单明细'
        verbose_name_plural = '采购单明细管理'
        ordering = ['purchase_order', 'id']

    def __str__(self):
        return f"{self.purchase_order.order_number} - {self.material.name}"

    @property
    def subtotal(self):
        """小计金额"""
        return self.quantity * self.unit_price

    @property
    def remaining_quantity(self):
        """剩余需要收货的数量"""
        return max(0, self.quantity - self.received_quantity)
