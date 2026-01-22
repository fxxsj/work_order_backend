"""
销售订单相关模型

包含销售订单管理的相关模型：
- SalesOrder: 销售订单
- SalesOrderItem: 销售订单明细
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction

class SalesOrder(models.Model):
    """销售订单"""
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('submitted', '已提交'),
        ('approved', '已审核'),
        ('in_production', '生产中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('unpaid', '未付款'),
        ('partial', '部分付款'),
        ('paid', '已付款'),
    ]

    @staticmethod
    def generate_order_number():
        """生成销售订单号：SO + yyyymmdd + 4位序号"""
        today = timezone.now().strftime('%Y%m%d')
        prefix = f'SO{today}'
        with transaction.atomic():
            latest = SalesOrder.objects.filter(
                order_number__startswith=prefix
            ).select_for_update().order_by('-order_number').first()
            if latest:
                last_number = int(latest.order_number[-4:])
                new_number = last_number + 1
            else:
                new_number = 1
            return f'{prefix}{new_number:04d}'

    order_number = models.CharField('销售订单号', max_length=50, unique=True)
    customer = models.ForeignKey('workorder.Customer', on_delete=models.PROTECT, verbose_name='客户')
    status = models.CharField('订单状态', max_length=20, choices=STATUS_CHOICES, default='draft')
    payment_status = models.CharField('付款状态', max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')

    # 金额信息
    subtotal = models.DecimalField('小计', max_digits=12, decimal_places=2, default=0,
                                   help_text='订单明细总金额')
    tax_rate = models.DecimalField('税率', max_digits=5, decimal_places=2, default=0,
                                    help_text='税率，如0.13表示13%')
    tax_amount = models.DecimalField('税额', max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField('折扣金额', max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField('订单总金额', max_digits=12, decimal_places=2, default=0)

    # 订单日期
    order_date = models.DateField('订单日期', default=timezone.now)
    delivery_date = models.DateField('预计交货日期')
    actual_delivery_date = models.DateField('实际交货日期', null=True, blank=True)

    # 付款信息
    deposit_amount = models.DecimalField('定金', max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField('已付金额', max_digits=12, decimal_places=2, default=0)
    payment_date = models.DateField('付款日期', null=True, blank=True)

    # 审核相关
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='submitted_sales_orders', verbose_name='提交人')
    submitted_at = models.DateTimeField('提交时间', null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='approved_sales_orders', verbose_name='审核人')
    approved_at = models.DateTimeField('审核时间', null=True, blank=True)
    approval_comment = models.TextField('审核意见', blank=True)

    # 关联施工单（一个销售订单可能需要多个施工单）
    work_orders = models.ManyToManyField('workorder.WorkOrder', blank=True, verbose_name='关联施工单')

    # 其他信息
    contact_person = models.CharField('联系人', max_length=100, blank=True)
    contact_phone = models.CharField('联系电话', max_length=50, blank=True)
    shipping_address = models.TextField('送货地址', blank=True)
    notes = models.TextField('备注', blank=True)
    rejection_reason = models.TextField('拒绝原因', blank=True,
                                       help_text='如果订单被拒绝，填写拒绝原因')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_sales_orders', verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '销售订单'
        verbose_name_plural = '销售订单管理'
        ordering = ['-created_at']
        permissions = [
            ('change_approved_salesorder', '可以编辑已审核的销售订单'),
        ]

    def __str__(self):
        return f"{self.order_number} - {self.customer.name}"

    def save(self, *args, **kwargs):
        """保存销售订单，自动生成订单号和计算金额"""
        if not self.order_number:
            self.order_number = self.generate_order_number()

        # 自动计算税额和总金额（仅在不是 update_fields 时计算）
        update_fields = kwargs.get('update_fields')
        if update_fields is None:
            self.tax_amount = self.subtotal * (self.tax_rate / 100)
            self.total_amount = self.subtotal + self.tax_amount - self.discount_amount

            # 根据已付金额更新付款状态
            if self.total_amount > 0:
                if self.paid_amount >= self.total_amount:
                    self.payment_status = 'paid'
                elif self.paid_amount > 0:
                    self.payment_status = 'partial'
                else:
                    self.payment_status = 'unpaid'

        super().save(*args, **kwargs)

    def update_totals(self):
        """更新订单总金额（从订单明细汇总）"""
        from django.db.models import Sum

        items_total = self.items.aggregate(
            subtotal_sum=Sum('subtotal')
        )['subtotal_sum'] or 0

        discount_total = self.items.aggregate(
            discount_sum=Sum('discount_amount')
        )['discount_sum'] or 0

        self.subtotal = items_total
        self.discount_amount = discount_total
        self.tax_amount = items_total * (self.tax_rate / 100)
        self.total_amount = items_total + self.tax_amount - discount_total

        self.save(update_fields=['subtotal', 'tax_amount', 'discount_amount', 'total_amount'])

    def validate_before_approval(self):
        """审核前验证销售订单数据完整性

        Returns:
            list: 错误信息列表，如果为空则表示验证通过
        """
        errors = []

        # 检查客户
        if not self.customer:
            errors.append('缺少客户信息')

        # 检查订单明细
        if not self.items.exists():
            errors.append('缺少订单明细')

        # 检查交货日期
        if not self.delivery_date:
            errors.append('缺少交货日期')

        # 检查订单日期和交货日期
        if self.order_date and self.delivery_date:
            if self.delivery_date < self.order_date:
                errors.append(f'交货日期不能早于订单日期。交货日期：{self.delivery_date}，订单日期：{self.order_date}')

        return errors


class SalesOrderItem(models.Model):
    """销售订单明细"""
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE,
                                  related_name='items', verbose_name='销售订单')
    product = models.ForeignKey('workorder.Product', on_delete=models.PROTECT, verbose_name='产品')
    quantity = models.IntegerField('数量')
    delivered_quantity = models.DecimalField('已发货数量', max_digits=10, decimal_places=2, default=0,
                                              help_text='已通过发货单发出的数量')
    unit = models.CharField('单位', max_length=20, default='件')
    unit_price = models.DecimalField('单价', max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField('税率', max_digits=5, decimal_places=2, default=0,
                                    help_text='该明细的税率，默认使用订单税率')
    discount_amount = models.DecimalField('折扣金额', max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField('小计', max_digits=12, decimal_places=2, default=0)
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    @property
    def remaining_quantity(self):
        """待发货数量"""
        return self.quantity - self.delivered_quantity

    @property
    def is_fully_delivered(self):
        """是否已全部发货"""
        return self.delivered_quantity >= self.quantity

    class Meta:
        verbose_name = '销售订单明细'
        verbose_name_plural = '销售订单明细管理'
        ordering = ['sales_order', 'id']

    def __str__(self):
        return f"{self.sales_order.order_number} - {self.product.name}"

    def save(self, *args, **kwargs):
        # 自动计算小计
        self.subtotal = self.quantity * self.unit_price - self.discount_amount
        super().save(*args, **kwargs)

