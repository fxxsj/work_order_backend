from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from datetime import datetime


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


class Process(models.Model):
    """工序定义"""
    name = models.CharField('工序名称', max_length=100)
    code = models.CharField('工序编码', max_length=50, unique=True)
    description = models.TextField('工序描述', blank=True)
    standard_duration = models.IntegerField('标准工时(小时)', default=0)
    sort_order = models.IntegerField('排序', default=0)
    is_active = models.BooleanField('是否启用', default=True)
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


class ProductMaterial(models.Model):
    """产品默认物料配置"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, 
                               related_name='default_materials', verbose_name='产品')
    material = models.ForeignKey('Material', on_delete=models.PROTECT, verbose_name='物料')
    material_size = models.CharField('尺寸', max_length=100, blank=True, help_text='如：A4、210x297mm等')
    material_usage = models.CharField('用量', max_length=100, blank=True, help_text='如：1000张、50平方米等')
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
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '物料'
        verbose_name_plural = '物料管理'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Artwork(models.Model):
    """图稿信息"""
    code = models.CharField('图稿编码', max_length=50, unique=True, blank=True, editable=False)
    name = models.CharField('图稿名称', max_length=200)
    # CMYK颜色选择（多选）
    cmyk_colors = models.JSONField('CMYK颜色', default=list, blank=True, 
                                   help_text='选中的CMYK颜色，如：["C", "M", "K"]')
    # 其他颜色（数组，每个颜色一个输入框）
    other_colors = models.JSONField('其他颜色', default=list, blank=True, 
                                   help_text='其他颜色列表，如：["528C", "金色"]')
    imposition_size = models.CharField('拼版尺寸', max_length=100, blank=True, help_text='如：420x594mm、889x1194mm等')
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '图稿'
        verbose_name_plural = '图稿管理'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @classmethod
    def generate_code(cls):
        """生成图稿编码：格式 ART + yyyymm + 3位自增序号"""
        now = timezone.now()
        prefix = f"ART{now.strftime('%Y%m')}"
        
        with transaction.atomic():
            last_artwork = cls.objects.filter(
                code__startswith=prefix
            ).order_by('-code').select_for_update().first()
            
            if last_artwork and len(last_artwork.code) >= 12:
                try:
                    last_number = int(last_artwork.code[9:])  # ART + yyyymm = 9位
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1
            else:
                new_number = 1
            
            return f"{prefix}{new_number:03d}"
    
    def save(self, *args, **kwargs):
        """保存时自动生成图稿编码"""
        if not self.code:
            self.code = self.generate_code()
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
    
    # 产品关联（兼容旧数据，保留单个产品字段）
    product = models.ForeignKey('Product', on_delete=models.PROTECT, verbose_name='产品', null=True, blank=True,
                               help_text='单个产品（兼容旧数据，建议使用 products 关联）')
    product_name = models.CharField('产品名称', max_length=200, blank=True)  # 保留字段用于兼容
    specification = models.TextField('产品规格', blank=True)
    quantity = models.IntegerField('数量', default=1)
    unit = models.CharField('单位', max_length=20, default='件')
    
    # 产品组关联（支持一个产品需要多个施工单的场景）
    product_group_item = models.ForeignKey('ProductGroupItem', on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='work_orders', verbose_name='产品组子项',
                                          help_text='如果该施工单是产品组的一部分，关联到对应的子产品')
    
    # 图稿和刀模关联
    artworks = models.ManyToManyField('Artwork', blank=True,
                                      related_name='work_orders', verbose_name='图稿（CTP版）',
                                      help_text='关联的图稿，用于CTP制版，支持多个图稿（如纸卡双面印刷的面版和底版）')
    dies = models.ManyToManyField('Die', blank=True,
                                  related_name='work_orders', verbose_name='刀模',
                                  help_text='关联的刀模，用于模切工序，支持多个刀模')
    
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

    def __str__(self):
        return f"{self.order_number} - {self.product_name}"

    def get_progress_percentage(self):
        """计算进度百分比"""
        total_processes = self.order_processes.count()
        if total_processes == 0:
            return 0
        completed_processes = self.order_processes.filter(status='completed').count()
        return int((completed_processes / total_processes) * 100)
    
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


class WorkOrderTask(models.Model):
    """施工单任务（为工序生成的具体任务）"""
    work_order_process = models.ForeignKey(WorkOrderProcess, on_delete=models.CASCADE,
                                          related_name='tasks', verbose_name='工序')
    work_content = models.TextField('施工内容', help_text='具体的施工内容描述')
    production_quantity = models.IntegerField('生产数量', default=0, help_text='该任务需要生产的数量')
    production_requirements = models.TextField('生产要求', blank=True, help_text='生产过程中的特殊要求')
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

