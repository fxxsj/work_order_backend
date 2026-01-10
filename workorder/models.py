from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from django.db.models import Max
from datetime import datetime

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


class Customer(models.Model):
    """客户信息"""
    name = models.CharField('客户名称', max_length=200)
    contact_person = models.CharField('联系人', max_length=100, blank=True)
    phone = models.CharField('联系电话', max_length=50, blank=True)
    email = models.EmailField('邮箱', blank=True)
    address = models.TextField('地址', blank=True)
    salesperson = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='customers', verbose_name='业务员',
                                    help_text='负责该客户的业务员')
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '客户'
        verbose_name_plural = '客户管理'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Department(models.Model):
    """部门"""
    name = models.CharField('部门名称', max_length=50, unique=True)
    code = models.CharField('部门编码', max_length=20, unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='children', verbose_name='上级部门',
                               help_text='上级部门，用于建立部门层级关系（如生产部下有多个车间）')
    sort_order = models.IntegerField('排序', default=0)
    is_active = models.BooleanField('是否启用', default=True)
    processes = models.ManyToManyField('Process', blank=True, verbose_name='工序',
                                       help_text='该部门负责的工序')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '部门'
        verbose_name_plural = '部门管理'
        ordering = ['sort_order', 'code']

    def __str__(self):
        return self.name
    
    def get_full_name(self):
        """获取完整名称（包含上级部门）"""
        if self.parent:
            return f"{self.parent.name} - {self.name}"
        return self.name
    
    def natural_key(self):
        """自然键：用于 fixtures 序列化"""
        return (self.code,)
    
    @classmethod
    def get_by_natural_key(cls, code):
        """通过自然键获取对象：用于 fixtures 反序列化"""
        return cls.objects.get(code=code)


class Process(models.Model):
    """工序定义"""
    TASK_GENERATION_RULE_CHOICES = [
        ('artwork', '按图稿生成任务（每个图稿一个任务，数量为1）'),
        ('die', '按刀模生成任务（每个刀模一个任务，数量为1）'),
        ('product', '按产品生成任务（每个产品一个任务）'),
        ('material', '按物料生成任务（每个物料一个任务）'),
        ('general', '生成通用任务（一个工序一个任务）'),
    ]
    
    name = models.CharField('工序名称', max_length=100)
    code = models.CharField('工序编码', max_length=50, unique=True)
    description = models.TextField('工序描述', blank=True)
    standard_duration = models.IntegerField('标准工时(小时)', default=0)
    sort_order = models.IntegerField('排序', default=0)
    is_active = models.BooleanField('是否启用', default=True)
    is_builtin = models.BooleanField('是否内置', default=False, 
                                    help_text='内置工序不可删除，code字段不可编辑')
    task_generation_rule = models.CharField('任务生成规则', max_length=20, 
                                           choices=TASK_GENERATION_RULE_CHOICES,
                                           default='general',
                                           help_text='该工序如何生成任务')
    # 工序需要的版（配置化）
    requires_artwork = models.BooleanField('需要图稿', default=False,
                                          help_text='该工序是否需要图稿（CTP版）')
    requires_die = models.BooleanField('需要刀模', default=False,
                                      help_text='该工序是否需要刀模')
    requires_foiling_plate = models.BooleanField('需要烫金版', default=False,
                                                 help_text='该工序是否需要烫金版')
    requires_embossing_plate = models.BooleanField('需要压凸版', default=False,
                                                   help_text='该工序是否需要压凸版')
    # 版是否必选（如果为False，则版可选，但需要手动创建设计任务，因为设计不属于施工单工序）
    artwork_required = models.BooleanField('图稿必选', default=True,
                                          help_text='如果为True，选择该工序时必须选择图稿；如果为False，图稿可选（但需要手动创建设计任务，设计不属于施工单工序）')
    die_required = models.BooleanField('刀模必选', default=True,
                                      help_text='如果为True，选择该工序时必须选择刀模；如果为False，刀模可选（但需要手动创建设计任务，设计不属于施工单工序）')
    foiling_plate_required = models.BooleanField('烫金版必选', default=True,
                                                 help_text='如果为True，选择该工序时必须选择烫金版；如果为False，烫金版可选（但需要手动创建设计任务，设计不属于施工单工序）')
    embossing_plate_required = models.BooleanField('压凸版必选', default=True,
                                                  help_text='如果为True，选择该工序时必须选择压凸版；如果为False，压凸版可选（但需要手动创建设计任务，设计不属于施工单工序）')
    is_parallel = models.BooleanField('可并行执行', default=False,
                                     help_text='该工序是否可以与其他工序并行执行（如制版、模切等）')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '工序'
        verbose_name_plural = '工序管理'
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Product(models.Model):
    """产品信息"""
    name = models.CharField('产品名称', max_length=200)
    code = models.CharField('产品编码', max_length=50, unique=True)
    specification = models.CharField('规格', max_length=200, blank=True)
    unit = models.CharField('单位', max_length=20, default='件')
    unit_price = models.DecimalField('单价', max_digits=10, decimal_places=2, default=0)
    stock_quantity = models.IntegerField('库存数量', default=0, help_text='产品的当前库存数量')
    min_stock_quantity = models.IntegerField('最小库存', default=0,
                                          help_text='库存低于此数量时触发预警')

    # 默认工序（多对多关系）
    default_processes = models.ManyToManyField('Process', blank=True, verbose_name='默认工序',
                                               help_text='创建施工单时将自动添加这些工序')

    description = models.TextField('产品描述', blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '产品'
        verbose_name_plural = '产品管理'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def is_low_stock(self):
        """检查库存是否不足"""
        return self.stock_quantity < self.min_stock_quantity

    def add_stock(self, quantity, user=None, reason=''):
        """增加库存数量"""
        if quantity <= 0:
            return False

        old_quantity = self.stock_quantity
        self.stock_quantity += quantity
        self.save(update_fields=['stock_quantity'])

        # 创建库存变更日志
        from .models import ProductStockLog
        ProductStockLog.objects.create(
            product=self,
            change_type='add',
            quantity=quantity,
            old_quantity=old_quantity,
            new_quantity=self.stock_quantity,
            reason=reason,
            created_by=user
        )

        # 检查是否需要预警
        if self.is_low_stock():
            self._send_low_stock_warning()

        return True

    def reduce_stock(self, quantity, user=None, reason=''):
        """减少库存数量"""
        if quantity <= 0:
            return False

        if self.stock_quantity < quantity:
            # 库存不足
            raise ValueError(f"库存不足：当前库存{self.stock_quantity}，需要{quantity}")

        old_quantity = self.stock_quantity
        self.stock_quantity -= quantity
        self.save(update_fields=['stock_quantity'])

        # 创建库存变更日志
        from .models import ProductStockLog
        ProductStockLog.objects.create(
            product=self,
            change_type='reduce',
            quantity=-quantity,
            old_quantity=old_quantity,
            new_quantity=self.stock_quantity,
            reason=reason,
            created_by=user
        )

        # 检查是否需要预警
        if self.is_low_stock():
            self._send_low_stock_warning()

        return True

    def _send_low_stock_warning(self):
        """发送库存预警通知"""
        from .models import Notification
        # 向所有具有库存预警权限的用户发送通知
        # 这里简化为向系统管理员发送
        from django.contrib.auth.models import User
        admins = User.objects.filter(is_superuser=True)
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                notification_type='low_stock_warning',
                title=f'产品库存预警：{self.name}',
                content=f'产品【{self.code} - {self.name}】的库存已低于预警值。当前库存：{self.stock_quantity}，最小库存：{self.min_stock_quantity}。请及时补货。',
                priority='high'
            )


class ProductStockLog(models.Model):
    """产品库存变更日志"""
    CHANGE_TYPE_CHOICES = [
        ('add', '入库'),
        ('reduce', '出库'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, 
                              related_name='stock_logs', verbose_name='产品')
    change_type = models.CharField('变更类型', max_length=20, choices=CHANGE_TYPE_CHOICES)
    quantity = models.IntegerField('变更数量', help_text='正数表示入库，负数表示出库')
    old_quantity = models.IntegerField('变更前库存')
    new_quantity = models.IntegerField('变更后库存')
    reason = models.TextField('变更原因', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='product_stock_logs', verbose_name='操作人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '产品库存日志'
        verbose_name_plural = '产品库存日志管理'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} - {self.get_change_type_display()}: {self.quantity}"


class ProductMaterial(models.Model):
    """产品默认物料配置"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, 
                               related_name='default_materials', verbose_name='产品')
    material = models.ForeignKey('Material', on_delete=models.PROTECT, verbose_name='物料')
    material_size = models.CharField('尺寸', max_length=100, blank=True, help_text='如：A4、210x297mm等')
    material_usage = models.CharField('用量', max_length=100, blank=True, help_text='如：1000张、50平方米等')
    need_cutting = models.BooleanField('需要开料', default=False, 
                                      help_text='该物料是否需要开料工序处理')
    notes = models.TextField('备注', blank=True)
    sort_order = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '产品默认物料'
        verbose_name_plural = '产品默认物料管理'
        ordering = ['product', 'sort_order']
        unique_together = ['product', 'material']

    def __str__(self):
        return f"{self.product.name} - {self.material.name}"


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
    work_order = models.ForeignKey('WorkOrder', on_delete=models.SET_NULL, null=True, blank=True,
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
    work_order_material = models.ForeignKey('WorkOrderMaterial', on_delete=models.SET_NULL,
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


class Artwork(models.Model):
    """图稿信息"""
    base_code = models.CharField('图稿主编码', max_length=50, blank=True, null=True, editable=False,
                                help_text='图稿的主编码，如：ART202412001，不包含版本号')
    version = models.IntegerField('版本号', default=1, help_text='图稿版本号，从1开始递增')
    name = models.CharField('图稿名称', max_length=200)
    # CMYK颜色选择（多选）
    cmyk_colors = models.JSONField('CMYK颜色', default=list, blank=True, 
                                   help_text='选中的CMYK颜色，如：["C", "M", "K"]')
    # 其他颜色（数组，每个颜色一个输入框）
    other_colors = models.JSONField('其他颜色', default=list, blank=True, 
                                   help_text='其他颜色列表，如：["528C", "金色"]')
    imposition_size = models.CharField('拼版尺寸', max_length=100, blank=True, help_text='如：420x594mm、889x1194mm等')
    # 关联刀模（多对多关系）
    dies = models.ManyToManyField('Die', blank=True, verbose_name='关联刀模',
                                 help_text='该图稿关联的刀模')
    # 关联烫金版（多对多关系）
    foiling_plates = models.ManyToManyField('FoilingPlate', blank=True, verbose_name='关联烫金版',
                                           help_text='该图稿关联的烫金版')
    # 关联压凸版（多对多关系）
    embossing_plates = models.ManyToManyField('EmbossingPlate', blank=True, verbose_name='关联压凸版',
                                              help_text='该图稿关联的压凸版')
    # 图稿确认相关字段
    confirmed = models.BooleanField('已确认', default=False, help_text='设计部是否已确认该图稿')
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='confirmed_artworks', verbose_name='确认人')
    confirmed_at = models.DateTimeField('确认时间', null=True, blank=True)
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '图稿'
        verbose_name_plural = '图稿管理'
        ordering = ['-base_code', '-version']
        unique_together = [['base_code', 'version']]  # 主编码+版本号组合唯一

    def __str__(self):
        return f"{self.get_full_code()} - {self.name}"
    
    def get_full_code(self):
        """获取完整编码（包含版本号）"""
        if self.version > 1:
            return f"{self.base_code}-v{self.version}"
        return self.base_code or ''
    
    @classmethod
    def generate_base_code(cls):
        """生成图稿主编码：格式 ART + yyyymm + 3位自增序号"""
        now = timezone.now()
        prefix = f"ART{now.strftime('%Y%m')}"
        
        with transaction.atomic():
            # 查找该前缀下的最大序号（不考虑版本号）
            last_artwork = cls.objects.filter(
                base_code__startswith=prefix
            ).order_by('-base_code').select_for_update().first()
            
            if last_artwork and last_artwork.base_code and len(last_artwork.base_code) >= 12:
                try:
                    last_number = int(last_artwork.base_code[9:])  # ART + yyyymm = 9位
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1
            else:
                new_number = 1
            
            return f"{prefix}{new_number:03d}"
    
    @classmethod
    def get_next_version(cls, base_code):
        """获取指定主编码的下一个版本号"""
        if not base_code:
            return 1
        max_version = cls.objects.filter(base_code=base_code).aggregate(
            max_version=Max('version')
        )['max_version']
        return (max_version or 0) + 1
    
    def save(self, *args, **kwargs):
        """保存时自动生成图稿主编码"""
        if not self.base_code:
            self.base_code = self.generate_base_code()
        super().save(*args, **kwargs)


class ArtworkProduct(models.Model):
    """图稿产品关联（包含拼版数量）"""
    artwork = models.ForeignKey(Artwork, on_delete=models.CASCADE,
                               related_name='products', verbose_name='图稿')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='产品')
    imposition_quantity = models.IntegerField('拼版数量', default=1, help_text='该产品在图稿中的拼版数量')
    sort_order = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '图稿产品'
        verbose_name_plural = '图稿产品管理'
        ordering = ['artwork', 'sort_order']
        unique_together = ['artwork', 'product']

    def __str__(self):
        return f"{self.artwork.name} - {self.product.name} ({self.imposition_quantity}拼)"


class Die(models.Model):
    """刀模信息"""
    code = models.CharField('刀模编码', max_length=50, unique=True, blank=True)
    name = models.CharField('刀模名称', max_length=200)
    size = models.CharField('尺寸', max_length=100, blank=True, help_text='如：420x594mm、889x1194mm等')
    material = models.CharField('材质', max_length=100, blank=True, help_text='如：木板、胶板等')
    thickness = models.CharField('厚度', max_length=50, blank=True, help_text='如：3mm、5mm等')
    # 刀模确认相关字段
    confirmed = models.BooleanField('已确认', default=False, help_text='设计部是否已确认该刀模')
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='confirmed_dies', verbose_name='确认人')
    confirmed_at = models.DateTimeField('确认时间', null=True, blank=True)
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '刀模'
        verbose_name_plural = '刀模管理'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @classmethod
    def generate_code(cls):
        """生成刀模编码：格式 DIE + yyyymm + 3位自增序号"""
        now = timezone.now()
        prefix = f"DIE{now.strftime('%Y%m')}"
        
        with transaction.atomic():
            last_die = cls.objects.filter(
                code__startswith=prefix
            ).order_by('-code').select_for_update().first()
            
            if last_die and len(last_die.code) >= 12:
                try:
                    last_number = int(last_die.code[9:])  # DIE + yyyymm = 9位
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1
            else:
                new_number = 1
            
            return f"{prefix}{new_number:03d}"
    
    def save(self, *args, **kwargs):
        """保存时自动生成刀模编码"""
        if not self.code:
            self.code = self.generate_code()
        super().save(*args, **kwargs)


class DieProduct(models.Model):
    """刀模产品关联"""
    die = models.ForeignKey(Die, on_delete=models.CASCADE,
                           related_name='products', verbose_name='刀模')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='产品')
    quantity = models.IntegerField('数量', default=1, help_text='该产品在刀模中的数量')
    sort_order = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '刀模产品'
        verbose_name_plural = '刀模产品管理'
        ordering = ['die', 'sort_order']
        unique_together = ['die', 'product']

    def __str__(self):
        return f"{self.die.name} - {self.product.name} ({self.quantity}个)"


class FoilingPlate(models.Model):
    """烫金版信息"""
    FOILING_TYPE_CHOICES = [
        ('gold', '烫金'),
        ('silver', '烫银'),
    ]
    
    code = models.CharField('烫金版编码', max_length=50, unique=True, blank=True)
    name = models.CharField('烫金版名称', max_length=200)
    foiling_type = models.CharField('类型', max_length=20, choices=FOILING_TYPE_CHOICES, 
                                    default='gold', help_text='该版是烫金还是烫银')
    size = models.CharField('尺寸', max_length=100, blank=True, help_text='如：420x594mm、889x1194mm等')
    material = models.CharField('材质', max_length=100, blank=True, help_text='如：铜版、锌版等')
    thickness = models.CharField('厚度', max_length=50, blank=True, help_text='如：3mm、5mm等')
    # 烫金版确认相关字段
    confirmed = models.BooleanField('已确认', default=False, help_text='设计部是否已确认该烫金版')
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='confirmed_foiling_plates', verbose_name='确认人')
    confirmed_at = models.DateTimeField('确认时间', null=True, blank=True)
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '烫金版'
        verbose_name_plural = '烫金版管理'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @classmethod
    def generate_code(cls):
        """生成烫金版编码：格式 FP + yyyymm + 3位自增序号"""
        now = timezone.now()
        prefix = f"FP{now.strftime('%Y%m')}"
        
        with transaction.atomic():
            last_plate = cls.objects.filter(
                code__startswith=prefix
            ).order_by('-code').select_for_update().first()
            
            if last_plate and len(last_plate.code) >= 11:
                try:
                    last_number = int(last_plate.code[8:])  # FP + yyyymm = 8位
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1
            else:
                new_number = 1
            
            return f"{prefix}{new_number:03d}"
    
    def save(self, *args, **kwargs):
        """保存时自动生成烫金版编码"""
        if not self.code:
            self.code = self.generate_code()
        super().save(*args, **kwargs)


class FoilingPlateProduct(models.Model):
    """烫金版产品关联"""
    foiling_plate = models.ForeignKey(FoilingPlate, on_delete=models.CASCADE,
                                     related_name='products', verbose_name='烫金版')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='产品')
    quantity = models.IntegerField('数量', default=1, help_text='该产品在烫金版中的数量')
    sort_order = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '烫金版产品'
        verbose_name_plural = '烫金版产品管理'
        ordering = ['foiling_plate', 'sort_order']
        unique_together = ['foiling_plate', 'product']

    def __str__(self):
        return f"{self.foiling_plate.name} - {self.product.name} ({self.quantity}个)"


class EmbossingPlate(models.Model):
    """压凸版信息"""
    code = models.CharField('压凸版编码', max_length=50, unique=True, blank=True)
    name = models.CharField('压凸版名称', max_length=200)
    size = models.CharField('尺寸', max_length=100, blank=True, help_text='如：420x594mm、889x1194mm等')
    material = models.CharField('材质', max_length=100, blank=True, help_text='如：铜版、锌版等')
    thickness = models.CharField('厚度', max_length=50, blank=True, help_text='如：3mm、5mm等')
    # 压凸版确认相关字段
    confirmed = models.BooleanField('已确认', default=False, help_text='设计部是否已确认该压凸版')
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='confirmed_embossing_plates', verbose_name='确认人')
    confirmed_at = models.DateTimeField('确认时间', null=True, blank=True)
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '压凸版'
        verbose_name_plural = '压凸版管理'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @classmethod
    def generate_code(cls):
        """生成压凸版编码：格式 EP + yyyymm + 3位自增序号"""
        now = timezone.now()
        prefix = f"EP{now.strftime('%Y%m')}"
        
        with transaction.atomic():
            last_plate = cls.objects.filter(
                code__startswith=prefix
            ).order_by('-code').select_for_update().first()
            
            if last_plate and len(last_plate.code) >= 11:
                try:
                    last_number = int(last_plate.code[8:])  # EP + yyyymm = 8位
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1
            else:
                new_number = 1
            
            return f"{prefix}{new_number:03d}"
    
    def save(self, *args, **kwargs):
        """保存时自动生成压凸版编码"""
        if not self.code:
            self.code = self.generate_code()
        super().save(*args, **kwargs)


class EmbossingPlateProduct(models.Model):
    """压凸版产品关联"""
    embossing_plate = models.ForeignKey(EmbossingPlate, on_delete=models.CASCADE,
                                        related_name='products', verbose_name='压凸版')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='产品')
    quantity = models.IntegerField('数量', default=1, help_text='该产品在压凸版中的数量')
    sort_order = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '压凸版产品'
        verbose_name_plural = '压凸版产品管理'
        ordering = ['embossing_plate', 'sort_order']
        unique_together = ['embossing_plate', 'product']

    def __str__(self):
        return f"{self.embossing_plate.name} - {self.product.name} ({self.quantity}个)"


class ProductGroup(models.Model):
    """产品组（如：天地盒、套装等，一个产品组可能需要多个施工单完成）"""
    name = models.CharField('产品组名称', max_length=200)
    code = models.CharField('产品组编码', max_length=50, unique=True)
    description = models.TextField('描述', blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '产品组'
        verbose_name_plural = '产品组管理'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class ProductGroupItem(models.Model):
    """产品组中的子产品（如：天地盒中的天盒、地盒）"""
    product_group = models.ForeignKey(ProductGroup, on_delete=models.CASCADE,
                                     related_name='items', verbose_name='产品组')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='产品')
    item_name = models.CharField('子产品名称', max_length=200, help_text='如：天盒、地盒')
    sort_order = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '产品组子项'
        verbose_name_plural = '产品组子项管理'
        ordering = ['product_group', 'sort_order']
        unique_together = ['product_group', 'product']

    def __str__(self):
        return f"{self.product_group.name} - {self.item_name} ({self.product.name})"


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
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name='客户')
    
    # 产品组关联（支持一个产品需要多个施工单的场景）
    product_group_item = models.ForeignKey('ProductGroupItem', on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='work_orders', verbose_name='产品组子项',
                                          help_text='如果该施工单是产品组的一部分，关联到对应的子产品')
    
    # 图稿、刀模、烫金版、压凸版关联（根据工序选择自动显示和验证）
    artworks = models.ManyToManyField('Artwork', blank=True,
                                      related_name='work_orders', verbose_name='图稿（CTP版）',
                                      help_text='关联的图稿，用于CTP制版，支持多个图稿（如纸卡双面印刷的面版和底版）')
    dies = models.ManyToManyField('Die', blank=True,
                                  related_name='work_orders', verbose_name='刀模',
                                  help_text='关联的刀模，用于模切工序，支持多个刀模')
    # 关联烫金版和压凸版
    foiling_plates = models.ManyToManyField('FoilingPlate', blank=True,
                                            related_name='work_orders', verbose_name='烫金版',
                                            help_text='关联的烫金版，用于烫金工序，支持多个烫金版')
    embossing_plates = models.ManyToManyField('EmbossingPlate', blank=True,
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
    
    order_date = models.DateField('下单日期', default=timezone.now)
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
        """审核前验证施工单数据完整性（增强版）
        
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
        errors = []
        
        # ========== 基础信息验证 ==========
        
        # 检查客户信息
        if not self.customer:
            errors.append('缺少客户信息')
        
        # 检查产品信息
        if not self.products.exists():
            errors.append('缺少产品信息')
        
        # 检查工序信息
        if not self.order_processes.exists():
            errors.append('缺少工序信息')
        
        # 检查交货日期
        if not self.delivery_date:
            errors.append('缺少交货日期')
        
        # ========== 版与工序匹配验证 ==========
        
        # 获取所有选中的工序
        selected_processes = self.order_processes.values_list('process', flat=True)
        processes = Process.objects.filter(id__in=selected_processes, is_active=True)
        
        # 检查图稿
        processes_requiring_artwork = processes.filter(requires_artwork=True, artwork_required=True)
        if processes_requiring_artwork.exists() and not self.artworks.exists():
            process_names = ', '.join([p.name for p in processes_requiring_artwork])
            errors.append(f'选择了需要图稿的工序（{process_names}），请至少选择一个图稿')
        
        # 检查刀模
        processes_requiring_die = processes.filter(requires_die=True, die_required=True)
        if processes_requiring_die.exists() and not self.dies.exists():
            process_names = ', '.join([p.name for p in processes_requiring_die])
            errors.append(f'选择了需要刀模的工序（{process_names}），请至少选择一个刀模')
        
        # 检查烫金版
        processes_requiring_foiling_plate = processes.filter(requires_foiling_plate=True, foiling_plate_required=True)
        if processes_requiring_foiling_plate.exists() and not self.foiling_plates.exists():
            process_names = ', '.join([p.name for p in processes_requiring_foiling_plate])
            errors.append(f'选择了需要烫金版的工序（{process_names}），请至少选择一个烫金版')
        
        # 检查压凸版
        processes_requiring_embossing_plate = processes.filter(requires_embossing_plate=True, embossing_plate_required=True)
        if processes_requiring_embossing_plate.exists() and not self.embossing_plates.exists():
            process_names = ', '.join([p.name for p in processes_requiring_embossing_plate])
            errors.append(f'选择了需要压凸版的工序（{process_names}），请至少选择一个压凸版')
        
        # ========== 数量验证 ==========
        
        # 检查生产数量
        if self.production_quantity is None:
            errors.append('缺少生产数量')
        elif self.production_quantity <= 0:
            errors.append(f'生产数量必须大于0，当前值为{self.production_quantity}')
        
        # 检查产品数量总和
        if self.products.exists():
            total_product_quantity = sum([p.quantity or 0 for p in self.products.all()])
            if total_product_quantity <= 0:
                errors.append(f'产品数量总和必须大于0，当前总和为{total_product_quantity}')
        
        # ========== 日期验证 ==========
        
        # 检查交货日期是否早于下单日期
        if self.delivery_date and self.order_date:
            if self.delivery_date < self.order_date:
                errors.append(f'交货日期不能早于下单日期。交货日期：{self.delivery_date}，下单日期：{self.order_date}')
        
        # 检查交货日期是否在过去（允许今天）
        from django.utils import timezone
        today = timezone.now().date()
        if self.delivery_date and self.delivery_date < today:
            errors.append(f'交货日期不能早于今天。交货日期：{self.delivery_date}，今天：{today}')
        
        # ========== 物料验证 ==========
        
        # 检查是否有需要开料的物料但未填写用量
        if self.materials.exists():
            for material_item in self.materials.all():
                if material_item.need_cutting and not material_item.material_usage:
                    errors.append(f'物料"{material_item.material.name}"需要开料，请填写物料用量')
        
        # ========== 工序顺序验证 ==========
        
        # 检查制版工序是否在印刷工序之前
        processes_ordered = self.order_processes.filter(
            process__code__in=['CTP', 'PRT']
        ).select_related('process').order_by('sequence')
        
        ctp_sequence = None
        prt_sequence = None
        for wp in processes_ordered:
            if wp.process.code == 'CTP':
                ctp_sequence = wp.sequence
            elif wp.process.code == 'PRT':
                prt_sequence = wp.sequence
        
        if ctp_sequence is not None and prt_sequence is not None:
            if ctp_sequence > prt_sequence:
                errors.append('制版工序（CTP）应该在印刷工序（PRT）之前，请调整工序顺序')
        
        # 检查开料工序是否在印刷工序之前
        cut_sequence = None
        for wp in processes_ordered:
            if wp.process.code == 'CUT':
                cut_sequence = wp.sequence
        
        if cut_sequence is not None and prt_sequence is not None:
            if cut_sequence > prt_sequence:
                errors.append('开料工序（CUT）应该在印刷工序（PRT）之前，请调整工序顺序')
        
        return errors
    
    @classmethod
    def generate_order_number(cls):
        """生成施工单号：格式 yyyymm + 3位自增序号"""
        now = datetime.now()
        prefix = now.strftime('%Y%m')
        
        # 获取当月最大的单号
        with transaction.atomic():
            last_order = cls.objects.filter(
                order_number__startswith=prefix
            ).order_by('-order_number').select_for_update().first()
            
            if last_order:
                # 提取序号部分并加1
                last_number = int(last_order.order_number[6:])
                new_number = last_number + 1
            else:
                # 当月第一单
                new_number = 1
            
            # 生成新单号，序号部分补齐3位
            order_number = f"{prefix}{new_number:03d}"
            
            return order_number
    
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

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, 
                                   related_name='order_processes', verbose_name='施工单')
    process = models.ForeignKey(Process, on_delete=models.PROTECT, verbose_name='工序')
    department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True,
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

    def __str__(self):
        return f"{self.work_order.order_number} - {self.process.name}"
    
    def can_start(self):
        """判断该工序是否可以开始"""
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
        from .models import Notification
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
            from .models import TaskAssignmentRule
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
            from .models import TaskAssignmentRule
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
            from .models import Notification
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
        
        规则：
        - 包装任务完成时，将任务的完成数量增加到对应产品的库存中
        - 产品数量 = 任务的生产数量
        """
        from .models import Product

        # 获取所有包装任务
        packaging_tasks = self.tasks.filter(
            task_type='packaging',
            status='completed'
        )

        # 按产品分组汇总数量
        product_quantities = {}
        for task in packaging_tasks:
            if task.product:
                product_id = task.product.id
                if product_id not in product_quantities:
                    product_quantities[product_id] = 0
                # 计算实际需要入库的数量
                # 新增数量 = 当前总完成数量 - 上次已计入库存的数量
                actual_quantity_to_stock = task.quantity_completed - (task.stock_accounted_quantity or 0)
                if actual_quantity_to_stock > 0:
                    product_quantities[product_id] += actual_quantity_to_stock
                    # 更新已计入库存的数量
                    task.stock_accounted_quantity = task.quantity_completed
                    task.save(update_fields=['stock_accounted_quantity'])

        # 更新产品库存
        for product_id, quantity in product_quantities.items():
            try:
                product = Product.objects.get(id=product_id)
                product.add_stock(
                    quantity=quantity,
                    user=None,
                    reason=f'施工单{self.work_order.order_number}包装工序完成，入库{quantity}{product.unit}'
                )
            except Product.DoesNotExist:
                # 产品已被删除，忽略
                pass

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
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE,
                                   related_name='products', verbose_name='施工单')
    product = models.ForeignKey('Product', on_delete=models.PROTECT, verbose_name='产品')
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
    
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE,
                                   related_name='materials', verbose_name='施工单')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, verbose_name='物料')
    
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

    work_order_process = models.ForeignKey(WorkOrderProcess, on_delete=models.CASCADE,
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
    
    work_order_process = models.ForeignKey(WorkOrderProcess, on_delete=models.CASCADE,
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
    artwork = models.ForeignKey('Artwork', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='tasks', verbose_name='关联图稿')
    die = models.ForeignKey('Die', on_delete=models.CASCADE, null=True, blank=True,
                           related_name='tasks', verbose_name='关联刀模')
    product = models.ForeignKey('Product', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='tasks', verbose_name='关联产品')
    material = models.ForeignKey('Material', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='tasks', verbose_name='关联物料')
    foiling_plate = models.ForeignKey('FoilingPlate', on_delete=models.CASCADE, null=True, blank=True,
                                     related_name='tasks', verbose_name='关联烫金版')
    embossing_plate = models.ForeignKey('EmbossingPlate', on_delete=models.CASCADE, null=True, blank=True,
                                       related_name='tasks', verbose_name='关联压凸版')
    production_requirements = models.TextField('生产要求', blank=True, help_text='生产过程中的特殊要求')
    stock_accounted_quantity = models.IntegerField('已计入库存的完成数量', default=0, 
                                              help_text='该任务已计入产品库存的完成数量，用于编辑数量时计算差异')
    # 任务分派（任务级别的分派，支持精细化管理）
    assigned_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
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
                             choices=[('pending', '待开始'), ('in_progress', '进行中'), 
                                     ('completed', '已完成'), ('cancelled', '已取消')],
                             default='pending')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '施工单任务'
        verbose_name_plural = '施工单任务管理'
        ordering = ['work_order_process', 'created_at']

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
            
            self.save()
            return True
        return False


class UserProfile(models.Model):
    """用户扩展信息"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile',
                                verbose_name='用户')
    departments = models.ManyToManyField(Department, blank=True,
                                        verbose_name='所属部门', help_text='用户所属的部门（可多选）')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '用户扩展信息'
        verbose_name_plural = '用户扩展信息管理'

    def __str__(self):
        if self.pk and self.departments.exists():
            dept_names = ', '.join([dept.name for dept in self.departments.all()])
            return f"{self.user.username} - {dept_names}"
        return f"{self.user.username} - 未分配部门"


class WorkOrderApprovalLog(models.Model):
    """施工单审核历史记录"""
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE,
                                   related_name='approval_logs', verbose_name='施工单')
    approval_status = models.CharField('审核状态', max_length=20, 
                                     choices=WorkOrder.APPROVAL_STATUS_CHOICES)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                   null=True, blank=True,
                                   related_name='approval_logs', verbose_name='审核人')
    approved_at = models.DateTimeField('审核时间', auto_now_add=True)
    approval_comment = models.TextField('审核意见', blank=True, 
                                       help_text='审核意见或说明')
    rejection_reason = models.TextField('拒绝原因', blank=True, 
                                       help_text='审核拒绝时的拒绝原因')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '施工单审核历史'
        verbose_name_plural = '施工单审核历史管理'
        ordering = ['-approved_at', '-created_at']

    def __str__(self):
        status_display = dict(WorkOrder.APPROVAL_STATUS_CHOICES).get(self.approval_status, self.approval_status)
        return f"{self.work_order.order_number} - {status_display} - {self.approved_by.username if self.approved_by else '未知'}"


class Notification(models.Model):
    """系统通知"""
    NOTIFICATION_TYPE_CHOICES = [
        ('approval_passed', '审核通过'),
        ('approval_rejected', '审核拒绝'),
        ('reapproval_requested', '请求重新审核'),
        ('task_assigned', '任务分派'),
        ('task_due_soon', '任务即将到期'),
        ('process_completed', '工序完成'),
        ('workorder_completed', '施工单完成'),
        ('task_cancelled', '任务取消'),
        ('purchase_order_submitted', '采购单待审核'),
        ('purchase_order_approved', '采购单已批准'),
        ('purchase_order_rejected', '采购单已拒绝'),
        ('purchase_order_received', '采购单已收货'),
        ('low_stock_warning', '库存不足预警'),
        ('system', '系统通知'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', '低'),
        ('normal', '普通'),
        ('high', '高'),
        ('urgent', '紧急'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE,
                                 related_name='notifications', verbose_name='接收人')
    notification_type = models.CharField('通知类型', max_length=30, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField('标题', max_length=200)
    content = models.TextField('内容', help_text='通知详细内容')
    priority = models.CharField('优先级', max_length=10, choices=PRIORITY_CHOICES, default='normal')
    
    # 关联对象（可选，用于跳转到相关页面）
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, null=True, blank=True,
                                   related_name='notifications', verbose_name='关联施工单')
    work_order_process = models.ForeignKey(WorkOrderProcess, on_delete=models.CASCADE, null=True, blank=True,
                                         related_name='notifications', verbose_name='关联工序')
    task = models.ForeignKey('WorkOrderTask', on_delete=models.CASCADE, null=True, blank=True,
                            related_name='notifications', verbose_name='关联任务')
    purchase_order = models.ForeignKey('PurchaseOrder', on_delete=models.CASCADE, null=True, blank=True,
                                       related_name='notifications', verbose_name='关联采购单')
    
    # 通知状态
    is_read = models.BooleanField('已读', default=False)
    read_at = models.DateTimeField('阅读时间', null=True, blank=True)
    
    # 元数据
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    expires_at = models.DateTimeField('过期时间', null=True, blank=True,
                                     help_text='通知过期时间，过期后不再显示')
    
    class Meta:
        verbose_name = '系统通知'
        verbose_name_plural = '系统通知管理'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.recipient.username} - {self.title}"
    
    def mark_as_read(self):
        """标记为已读"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    @classmethod
    def create_notification(cls, recipient, notification_type, title, content, 
                           priority='normal', work_order=None, work_order_process=None, 
                           task=None, expires_at=None):
        """创建通知的便捷方法"""
        return cls.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            content=content,
            priority=priority,
            work_order=work_order,
            work_order_process=work_order_process,
            task=task,
            expires_at=expires_at
        )


class TaskAssignmentRule(models.Model):
    """任务分派规则配置"""
    OPERATOR_SELECTION_STRATEGY_CHOICES = [
        ('least_tasks', '任务数量最少（工作量均衡）'),
        ('random', '随机选择'),
        ('round_robin', '轮询分配'),
        ('first_available', '第一个可用'),
    ]
    
    process = models.ForeignKey(Process, on_delete=models.CASCADE,
                               related_name='assignment_rules', verbose_name='工序',
                               help_text='该规则适用的工序')
    department = models.ForeignKey(Department, on_delete=models.CASCADE,
                                  related_name='assignment_rules', verbose_name='分派部门',
                                  help_text='该工序应分派到的部门')
    priority = models.IntegerField('优先级', default=0,
                                  help_text='优先级越高越优先匹配（0-100）')
    operator_selection_strategy = models.CharField('操作员选择策略', max_length=20,
                                                   choices=OPERATOR_SELECTION_STRATEGY_CHOICES,
                                                   default='least_tasks',
                                                   help_text='从部门中选择操作员的策略')
    is_active = models.BooleanField('是否启用', default=True,
                                   help_text='是否启用该规则')
    notes = models.TextField('备注', blank=True,
                            help_text='规则说明或备注')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = '任务分派规则'
        verbose_name_plural = '任务分派规则管理'
        ordering = ['process', '-priority', 'department']
        unique_together = [['process', 'department']]  # 同一工序同一部门只能有一条规则

    def __str__(self):
        return f"{self.process.name} -> {self.department.name} (优先级:{self.priority})"


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
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name='客户')
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
    work_orders = models.ManyToManyField('WorkOrder', blank=True, verbose_name='关联施工单')

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
        if not self.order_number:
            self.order_number = self.generate_order_number()

        # 自动计算税额和总金额
        self.tax_amount = self.subtotal * self.tax_rate
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount

        # 根据已付金额更新付款状态
        if self.paid_amount >= self.total_amount:
            self.payment_status = 'paid'
        elif self.paid_amount > 0:
            self.payment_status = 'partial'
        else:
            self.payment_status = 'unpaid'

        super().save(*args, **kwargs)

    def update_totals(self):
        """从订单明细更新小计，并保存"""
        self.subtotal = sum(item.subtotal for item in self.items.all())
        self.save()

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
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='产品')
    quantity = models.IntegerField('数量')
    unit = models.CharField('单位', max_length=20, default='件')
    unit_price = models.DecimalField('单价', max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField('税率', max_digits=5, decimal_places=2, default=0,
                                    help_text='该明细的税率，默认使用订单税率')
    discount_amount = models.DecimalField('折扣金额', max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField('小计', max_digits=12, decimal_places=2, default=0)
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

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

