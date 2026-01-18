"""
财务相关模型

包含财务管理的相关模型：
- CostCenter: 成本中心
- CostItem: 成本项目
- ProductionCost: 生产成本
- Invoice: 发票
- Payment: 收款记录
- PaymentPlan: 收款计划
- Statement: 对账单
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum


class CostCenter(models.Model):
    """成本中心"""
    TYPE_CHOICES = [
        ('production', '生产部门'),
        ('auxiliary', '辅助部门'),
        ('management', '管理部门'),
        ('sales', '销售部门'),
    ]

    name = models.CharField('成本中心名称', max_length=100)
    code = models.CharField('成本中心编码', max_length=50, unique=True)
    type = models.CharField('类型', max_length=20, choices=TYPE_CHOICES, default='production')
    description = models.TextField('描述', blank=True)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='managed_cost_centers', verbose_name='负责人')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                              related_name='children', verbose_name='上级成本中心')
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '成本中心'
        verbose_name_plural = '成本中心管理'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class CostItem(models.Model):
    """成本项目"""
    TYPE_CHOICES = [
        ('material', '直接材料'),
        ('labor', '直接人工'),
        ('equipment', '设备折旧'),
        ('overhead', '制造费用'),
    ]

    ALLOCATION_METHOD_CHOICES = [
        ('direct', '直接分摊'),
        ('labor_hours', '按工时分摊'),
        ('machine_hours', '按机时分摊'),
        ('quantity', '按产量分摊'),
        ('value', '按产值分摊'),
    ]

    name = models.CharField('成本项目名称', max_length=100)
    code = models.CharField('成本项目编码', max_length=50, unique=True)
    type = models.CharField('类型', max_length=20, choices=TYPE_CHOICES)
    allocation_method = models.CharField('分摊方法', max_length=20, choices=ALLOCATION_METHOD_CHOICES,
                                        default='direct')
    description = models.TextField('描述', blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '成本项目'
        verbose_name_plural = '成本项目管理'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class ProductionCost(models.Model):
    """生产成本"""
    work_order = models.OneToOneField('workorder.WorkOrder', on_delete=models.CASCADE,
                                     related_name='production_cost', verbose_name='施工单')
    period = models.CharField('成本核算期', max_length=20, help_text='格式: 2024-01')

    # 成本明细
    material_cost = models.DecimalField('材料成本', max_digits=12, decimal_places=2, default=0)
    labor_cost = models.DecimalField('人工成本', max_digits=12, decimal_places=2, default=0)
    equipment_cost = models.DecimalField('设备成本', max_digits=12, decimal_places=2, default=0)
    overhead_cost = models.DecimalField('制造费用', max_digits=12, decimal_places=2, default=0)

    # 总成本
    total_cost = models.DecimalField('总成本', max_digits=12, decimal_places=2, default=0)

    # 对比分析
    standard_cost = models.DecimalField('标准成本', max_digits=12, decimal_places=2, default=0)
    variance = models.DecimalField('成本差异', max_digits=12, decimal_places=2, default=0)
    variance_rate = models.DecimalField('差异率', max_digits=5, decimal_places=2, default=0)

    # 成本核算信息
    calculated_at = models.DateTimeField('核算时间', null=True, blank=True)
    calculated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='calculated_costs', verbose_name='核算人')
    notes = models.TextField('备注', blank=True)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '生产成本'
        verbose_name_plural = '生产成本管理'
        ordering = ['-period']
        indexes = [
            models.Index(fields=['period']),
            models.Index(fields=['work_order']),
        ]

    def __str__(self):
        return f"{self.work_order.order_number} - {self.period}"

    def calculate_total_cost(self):
        """计算总成本"""
        self.total_cost = (
            self.material_cost +
            self.labor_cost +
            self.equipment_cost +
            self.overhead_cost
        )

        # 计算差异
        if self.standard_cost > 0:
            self.variance = self.total_cost - self.standard_cost
            self.variance_rate = (self.variance / self.standard_cost) * 100 if self.standard_cost else 0

        self.save()

    def auto_calculate_material_cost(self):
        """自动计算材料成本"""
        from workorder.models import WorkOrderMaterial
        materials = WorkOrderMaterial.objects.filter(work_order=self.work_order)
        total = 0
        for material in materials:
            if material.material:
                total += material.material_usage * material.material.unit_price
        self.material_cost = total
        self.save()

    def auto_calculate_labor_cost(self):
        """自动计算人工成本（基于工时）"""
        # TODO: 待工时管理模块实现后完善
        pass


class Invoice(models.Model):
    """发票"""
    TYPE_CHOICES = [
        ('vat_special', '增值税专用发票'),
        ('vat_normal', '增值税普通发票'),
        ('electronic', '电子发票'),
    ]

    STATUS_CHOICES = [
        ('draft', '待开具'),
        ('issued', '已开具'),
        ('sent', '已发送'),
        ('received', '已收到'),
        ('cancelled', '已作废'),
        ('refunded', '已红冲'),
    ]

    @staticmethod
    def generate_invoice_number():
        """生成发票号码：FP + yyyymmdd + 4位序号"""
        today = timezone.now().strftime('%Y%m%d')
        prefix = f'FP{today}'
        with transaction.atomic():
            latest = Invoice.objects.filter(
                invoice_number__startswith=prefix
            ).select_for_update().order_by('-invoice_number').first()
            if latest:
                last_number = int(latest.invoice_number[-4:])
                new_number = last_number + 1
            else:
                new_number = 1
            return f'{prefix}{new_number:04d}'

    invoice_number = models.CharField('发票号码', max_length=50, unique=True, editable=False)
    invoice_code = models.CharField('发票代码', max_length=50, blank=True)
    invoice_type = models.CharField('发票类型', max_length=20, choices=TYPE_CHOICES, default='vat_normal')

    # 关联信息
    sales_order = models.ForeignKey('workorder.SalesOrder', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='invoices', verbose_name='销售订单')
    work_order = models.ForeignKey('workorder.WorkOrder', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='invoices', verbose_name='施工单')
    customer = models.ForeignKey('workorder.Customer', on_delete=models.PROTECT, verbose_name='客户')

    # 金额信息
    amount = models.DecimalField('金额(不含税)', max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField('税率', max_digits=5, decimal_places=2, default=13)
    tax_amount = models.DecimalField('税额', max_digits=12, decimal_places=2)
    total_amount = models.DecimalField('价税合计', max_digits=12, decimal_places=2)

    # 开票信息
    issue_date = models.DateField('开票日期', null=True, blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='draft')

    # 客户开票信息
    customer_tax_number = models.CharField('客户税号', max_length=50, blank=True)
    customer_address = models.TextField('客户地址', blank=True)
    customer_phone = models.CharField('客户电话', max_length=50, blank=True)
    customer_bank = models.CharField('开户行', max_length=100, blank=True)
    customer_account = models.CharField('账号', max_length=50, blank=True)

    # 备注和附件
    notes = models.TextField('备注', blank=True)
    attachment = models.FileField('发票附件', upload_to='invoices/', null=True, blank=True)

    # 审核信息
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='submitted_invoices', verbose_name='提交人')
    submitted_at = models.DateTimeField('提交时间', null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='approved_invoices', verbose_name='审核人')
    approved_at = models.DateTimeField('审核时间', null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_invoices', verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '发票'
        verbose_name_plural = '发票管理'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['customer']),
            models.Index(fields=['issue_date']),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.customer.name}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()

        # 自动计算税额和价税合计
        self.tax_amount = self.amount * (self.tax_rate / 100)
        self.total_amount = self.amount + self.tax_amount

        super().save(*args, **kwargs)


class Payment(models.Model):
    """收款记录"""
    METHOD_CHOICES = [
        ('cash', '现金'),
        ('transfer', '转账'),
        ('check', '支票'),
        ('acceptance', '承兑汇票'),
    ]

    @staticmethod
    def generate_payment_number():
        """生成收款单号：SK + yyyymmdd + 4位序号"""
        today = timezone.now().strftime('%Y%m%d')
        prefix = f'SK{today}'
        with transaction.atomic():
            latest = Payment.objects.filter(
                payment_number__startswith=prefix
            ).select_for_update().order_by('-payment_number').first()
            if latest:
                last_number = int(latest.payment_number[-4:])
                new_number = last_number + 1
            else:
                new_number = 1
            return f'{prefix}{new_number:04d}'

    payment_number = models.CharField('收款单号', max_length=50, unique=True, editable=False)
    sales_order = models.ForeignKey('workorder.SalesOrder', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='payments', verbose_name='销售订单')
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='payments', verbose_name='关联发票')
    customer = models.ForeignKey('workorder.Customer', on_delete=models.PROTECT, verbose_name='客户')

    amount = models.DecimalField('收款金额', max_digits=12, decimal_places=2)
    payment_method = models.CharField('收款方式', max_length=20, choices=METHOD_CHOICES)
    payment_date = models.DateField('收款日期', default=timezone.now)

    # 银行信息
    bank_account = models.CharField('收款账户', max_length=50, blank=True)
    transaction_number = models.CharField('交易流水号', max_length=100, blank=True)

    # 核销信息
    applied_amount = models.DecimalField('核销金额', max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField('剩余金额', max_digits=12, decimal_places=2, default=0)

    notes = models.TextField('备注', blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='recorded_payments', verbose_name='记录人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '收款记录'
        verbose_name_plural = '收款管理'
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['payment_date']),
        ]

    def __str__(self):
        return f"{self.payment_number} - {self.customer.name}"

    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = self.generate_payment_number()

        # 计算剩余金额
        self.remaining_amount = self.amount - self.applied_amount

        super().save(*args, **kwargs)


class PaymentPlan(models.Model):
    """收款计划"""
    sales_order = models.ForeignKey('workorder.SalesOrder', on_delete=models.CASCADE,
                                   related_name='payment_plans', verbose_name='销售订单')
    plan_amount = models.DecimalField('计划金额', max_digits=12, decimal_places=2)
    plan_date = models.DateField('计划收款日期')
    status = models.CharField('状态', max_length=20,
                             choices=[('pending', '待收款'), ('partial', '部分收款'), ('completed', '已完成')],
                             default='pending')
    paid_amount = models.DecimalField('已收金额', max_digits=12, decimal_places=2, default=0)
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '收款计划'
        verbose_name_plural = '收款计划管理'
        ordering = ['plan_date']

    def __str__(self):
        return f"{self.sales_order.order_number} - {self.plan_date}"

    def update_status(self):
        """更新收款状态"""
        if self.paid_amount >= self.plan_amount:
            self.status = 'completed'
        elif self.paid_amount > 0:
            self.status = 'partial'
        else:
            self.status = 'pending'
        self.save()


class Statement(models.Model):
    """对账单"""
    TYPE_CHOICES = [
        ('customer', '客户对账单'),
        ('supplier', '供应商对账单'),
    ]

    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('sent', '已发送'),
        ('confirmed', '已确认'),
        ('disputed', '有异议'),
    ]

    @staticmethod
    def generate_statement_number():
        """生成对账单号：DZ + yyyymmdd + 4位序号"""
        today = timezone.now().strftime('%Y%m%d')
        prefix = f'DZ{today}'
        with transaction.atomic():
            latest = Statement.objects.filter(
                statement_number__startswith=prefix
            ).select_for_update().order_by('-statement_number').first()
            if latest:
                last_number = int(latest.statement_number[-4:])
                new_number = last_number + 1
            else:
                new_number = 1
            return f'{prefix}{new_number:04d}'

    statement_number = models.CharField('对账单号', max_length=50, unique=True, editable=False)
    statement_type = models.CharField('对账单类型', max_length=20, choices=TYPE_CHOICES, default='customer')
    customer = models.ForeignKey('workorder.Customer', on_delete=models.PROTECT, null=True, blank=True,
                                related_name='statements', verbose_name='客户')
    supplier = models.ForeignKey('workorder.Supplier', on_delete=models.PROTECT, null=True, blank=True,
                                related_name='statements', verbose_name='供应商')

    period = models.CharField('对账周期', max_length=20, help_text='格式: 2024-01')
    start_date = models.DateField('开始日期')
    end_date = models.DateField('结束日期')

    # 金额汇总
    opening_balance = models.DecimalField('期初余额', max_digits=12, decimal_places=2, default=0)
    total_debit = models.DecimalField('本期借方', max_digits=12, decimal_places=2, default=0)
    total_credit = models.DecimalField('本期贷方', max_digits=12, decimal_places=2, default=0)
    closing_balance = models.DecimalField('期末余额', max_digits=12, decimal_places=2, default=0)

    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='draft')

    # 确认信息
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='confirmed_statements', verbose_name='确认人')
    confirmed_at = models.DateTimeField('确认时间', null=True, blank=True)
    confirmation_notes = models.TextField('确认备注', blank=True)

    notes = models.TextField('备注', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_statements', verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '对账单'
        verbose_name_plural = '对账单管理'
        ordering = ['-period']

    def __str__(self):
        if self.customer:
            return f"{self.statement_number} - {self.customer.name} ({self.period})"
        return f"{self.statement_number} - {self.supplier.name} ({self.period})"

    def save(self, *args, **kwargs):
        if not self.statement_number:
            self.statement_number = self.generate_statement_number()

        # 计算期末余额
        self.closing_balance = self.opening_balance + self.total_debit - self.total_credit

        super().save(*args, **kwargs)
