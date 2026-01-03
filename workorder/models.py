from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from django.db.models import Max
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
    task_generation_rule = models.CharField('任务生成规则', max_length=20, 
                                           choices=TASK_GENERATION_RULE_CHOICES,
                                           default='general',
                                           help_text='该工序如何生成任务')
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
    need_cutting = models.BooleanField('需要开料', default=False, 
                                      help_text='该物料是否需要开料工序处理')
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
    base_code = models.CharField('图稿主编码', max_length=50, blank=True, editable=False,
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
    
    # 图稿类型选择
    ARTWORK_TYPE_CHOICES = [
        ('no_artwork', '不需要图稿'),
        ('new_design', '新设计图稿'),
        ('need_update', '需更新图稿'),
        ('old_artwork', '旧图稿'),
    ]
    artwork_type = models.CharField('图稿（CTP版）', max_length=20, choices=ARTWORK_TYPE_CHOICES,
                                    default='no_artwork', help_text='图稿类型选择')
    
    # 刀模类型选择
    DIE_TYPE_CHOICES = [
        ('no_die', '不需要刀模'),
        ('new_design', '新设计刀模'),
        ('need_update', '需更新刀模'),
        ('old_die', '旧刀模'),
    ]
    die_type = models.CharField('刀模', max_length=20, choices=DIE_TYPE_CHOICES,
                               default='no_die', help_text='刀模类型选择')
    
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
    
    def can_start(self):
        """判断该工序是否可以开始"""
        # 制版、刀模和采购可以并行（通过工序名称识别）
        process_name = self.process.name.lower()
        parallel_keywords = ['制版', '设计', '刀模', '模切', '采购']
        
        if any(keyword in process_name for keyword in parallel_keywords):
            # 这些工序可以并行，只要没有其他限制就可以开始
            return True
        
        # 其他工序需要前一个工序完成
        # 获取所有非并行工序，按 sequence 排序
        non_parallel_processes = WorkOrderProcess.objects.filter(
            work_order=self.work_order
        ).exclude(
            process__name__icontains='制版'
        ).exclude(
            process__name__icontains='设计'
        ).exclude(
            process__name__icontains='刀模'
        ).exclude(
            process__name__icontains='模切'
        ).exclude(
            process__name__icontains='采购'
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
        """根据任务状态自动判断工序是否完成"""
        all_tasks = self.tasks.all()
        if not all_tasks.exists():
            return False
        
        process_name = self.process.name.lower()
        rule = self.process.task_generation_rule
        
        # 根据任务生成规则和工序名称判断完成条件
        if rule == 'artwork':
            # 图稿任务：制版需要图稿确认+任务完成，印刷只需要任务完成
            if '制版' in process_name or '设计' in process_name:
                # 制版：检查所有图稿是否已确认且任务完成
                for task in all_tasks:
                    if task.artwork and not task.artwork.confirmed:
                        return False
                    if task.status != 'completed':
                        return False
            else:
                # 印刷等其他图稿任务：只需要任务完成
                for task in all_tasks:
                    if task.status != 'completed':
                        return False
        
        elif rule == 'material':
            # 物料任务：根据工序名称判断完成条件
            if '采购' in process_name:
                # 采购：检查所有物料是否已回料（purchase_status='received'）
                for task in all_tasks:
                    if task.material:
                        try:
                            material_record = WorkOrderMaterial.objects.get(
                                work_order=self.work_order,
                                material=task.material
                            )
                            if material_record.purchase_status != 'received':
                                return False
                        except WorkOrderMaterial.DoesNotExist:
                            return False
            elif '开料' in process_name or '裁切' in process_name:
                # 开料：检查所有物料是否已开料（purchase_status='cut'）
                for task in all_tasks:
                    if task.material:
                        try:
                            material_record = WorkOrderMaterial.objects.get(
                                work_order=self.work_order,
                                material=task.material
                            )
                            if material_record.purchase_status != 'cut':
                                return False
                        except WorkOrderMaterial.DoesNotExist:
                            return False
            else:
                # 其他物料任务：检查任务状态
                for task in all_tasks:
                    if task.status != 'completed':
                        return False
        
        elif rule == 'die':
            # 刀模任务（模切）：检查所有任务是否完成
            for task in all_tasks:
                if task.status != 'completed':
                    return False
        
        elif rule == 'product':
            # 产品任务（包装）：检查所有任务是否完成
            for task in all_tasks:
                if task.status != 'completed':
                    return False
        
        else:  # general
            # 通用任务（裱坑、打钉等）：检查所有任务是否完成
            for task in all_tasks:
                if task.status != 'completed':
                    return False
        
        # 如果所有任务完成，设置工序状态为 completed
        if all(task.status == 'completed' for task in all_tasks):
            self.status = 'completed'
            self.actual_end_time = timezone.now()
            self.save()
            return True
        return False
    
    def generate_tasks(self):
        """为工序生成任务（在工序开始时调用）"""
        # 如果已经有任务，不再生成
        if self.tasks.exists():
            return
        
        process = self.process
        work_order = self.work_order
        rule = process.task_generation_rule
        process_name = process.name.lower()
        
        # 根据任务生成规则生成任务
        if rule == 'artwork':
            # 按图稿生成任务（每个图稿一个任务，数量为1）
            # 用于：制版、印刷
            for artwork in work_order.artworks.all():
                # 根据工序名称确定任务内容
                if '制版' in process_name or '设计' in process_name:
                    work_content = f'制版：{artwork.get_full_code()} - {artwork.name}'
                elif '印刷' in process_name:
                    work_content = f'印刷：{artwork.get_full_code()} - {artwork.name}'
                else:
                    work_content = f'{process.name}：{artwork.get_full_code()} - {artwork.name}'
                
                WorkOrderTask.objects.create(
                    work_order_process=self,
                    task_type='artwork',
                    artwork=artwork,
                    work_content=work_content,
                    production_quantity=1,
                    quantity_completed=0,
                    auto_calculate_quantity=False  # 图稿任务固定为1
                )
        
        elif rule == 'die':
            # 按刀模生成任务（每个刀模一个任务，数量为1）
            # 用于：模切
            for die in work_order.dies.all():
                WorkOrderTask.objects.create(
                    work_order_process=self,
                    task_type='die',
                    die=die,
                    work_content=f'模切：{die.code} - {die.name}',
                    production_quantity=1,
                    quantity_completed=0,
                    auto_calculate_quantity=False  # 刀模任务固定为1
                )
        
        elif rule == 'product':
            # 按产品生成任务（每个产品一个任务）
            # 用于：包装
            for product_item in work_order.products.all():
                WorkOrderTask.objects.create(
                    work_order_process=self,
                    task_type='product',
                    product=product_item.product,
                    work_content=f'包装：{product_item.product.name}',
                    production_quantity=product_item.quantity,
                    quantity_completed=0,
                    auto_calculate_quantity=True
                )
        
        elif rule == 'material':
            # 按物料生成任务（每个物料一个任务）
            # 用于：采购、开料
            if '采购' in process_name:
                # 采购任务：所有物料
                for material_item in work_order.materials.all():
                    quantity = self._parse_material_usage(material_item.material_usage)
                    WorkOrderTask.objects.create(
                        work_order_process=self,
                        task_type='material',
                        material=material_item.material,
                        work_content=f'采购：{material_item.material.name}',
                        production_quantity=quantity,
                        quantity_completed=0,
                        auto_calculate_quantity=True
                    )
            elif '开料' in process_name or '裁切' in process_name:
                # 开料任务：只包含需要开料的物料（need_cutting=True）
                for material_item in work_order.materials.all():
                    if material_item.material.need_cutting:
                        quantity = self._parse_material_usage(material_item.material_usage)
                        WorkOrderTask.objects.create(
                            work_order_process=self,
                            task_type='material',
                            material=material_item.material,
                            work_content=f'开料：{material_item.material.name}',
                            production_quantity=quantity,
                            quantity_completed=0,
                            auto_calculate_quantity=True
                        )
            else:
                # 其他物料相关工序
                for material_item in work_order.materials.all():
                    quantity = self._parse_material_usage(material_item.material_usage)
                    WorkOrderTask.objects.create(
                        work_order_process=self,
                        task_type='material',
                        material=material_item.material,
                        work_content=f'{process.name}：{material_item.material.name}',
                        production_quantity=quantity,
                        quantity_completed=0,
                        auto_calculate_quantity=True
                    )
        
        else:  # general
            # 生成通用任务（一个工序一个任务）
            # 用于：裱坑、打钉等其他工序
            WorkOrderTask.objects.create(
                work_order_process=self,
                task_type='general',
                work_content=f'{process.name}：{work_order.order_number}',
                production_quantity=work_order.production_quantity or 0,
                quantity_completed=0,
                auto_calculate_quantity=True
            )
    
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


class WorkOrderTask(models.Model):
    """施工单任务（为工序生成的具体任务）"""
    TASK_TYPE_CHOICES = [
        ('artwork', '图稿任务'),
        ('die', '刀模任务'),
        ('product', '产品任务'),
        ('material', '物料任务'),
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


class UserProfile(models.Model):
    """用户扩展信息"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile',
                                verbose_name='用户')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='所属部门', help_text='用户所属的部门')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '用户扩展信息'
        verbose_name_plural = '用户扩展信息管理'

    def __str__(self):
        return f"{self.user.username} - {self.department.name if self.department else '未分配部门'}"

