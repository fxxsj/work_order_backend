"""
基础数据模型

包含系统的基础数据模型：
- Customer: 客户信息
- Department: 部门信息
- Process: 工序定义
"""

from django.db import models
from django.contrib.auth.models import User


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

        # 性能优化：为高频查询字段添加索引
        indexes = [
            models.Index(fields=['name'], name='customer_name_idx'),
            models.Index(fields=['phone'], name='customer_phone_idx'),
            models.Index(fields=['salesperson'], name='customer_salesperson_idx'),
        ]

    def __str__(self):
        return self.name


class Department(models.Model):
    """部门

    部门信息管理，支持层级结构（最多3级）。

    Attributes:
        name: 部门名称，唯一
        code: 部门编码，唯一，只能包含小写字母、数字和下划线
        parent: 上级部门，用于建立层级关系
        sort_order: 排序值，数字越小越靠前
        is_active: 是否启用
        processes: 该部门负责的工序
    """
    name = models.CharField(
        '部门名称',
        max_length=50,
        unique=True,
        help_text='部门名称，必须唯一'
    )
    code = models.CharField(
        '部门编码',
        max_length=20,
        unique=True,
        help_text='部门编码，只能包含小写字母、数字和下划线'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级部门',
        help_text='上级部门，用于建立部门层级关系（如生产部下有多个车间）'
    )
    sort_order = models.IntegerField(
        '排序',
        default=0,
        help_text='排序值，数字越小越靠前'
    )
    is_active = models.BooleanField(
        '是否启用',
        default=True,
        help_text='禁用后部门将不可用于新的施工单'
    )
    processes = models.ManyToManyField(
        'Process',
        blank=True,
        verbose_name='工序',
        help_text='该部门负责的工序'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '部门'
        verbose_name_plural = '部门管理'
        ordering = ['sort_order', 'code']

        # 性能优化：为高频查询字段添加索引
        indexes = [
            models.Index(fields=['name'], name='department_name_idx'),
            models.Index(fields=['code'], name='department_code_idx'),
            models.Index(fields=['is_active'], name='department_is_active_idx'),
            models.Index(fields=['sort_order'], name='department_sort_order_idx'),
            models.Index(
                fields=['is_active', 'sort_order'],
                name='dept_active_sort_idx'
            ),
        ]

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

    def get_ancestors(self):
        """获取所有祖先部门（从直接上级到顶级）

        Returns:
            list: 祖先部门列表，按层级从近到远排序
        """
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors

    def get_descendants(self):
        """获取所有子孙部门（递归）

        Returns:
            list: 子孙部门列表
        """
        descendants = []
        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants

    def get_level(self):
        """获取部门层级（顶级为0）

        Returns:
            int: 层级深度
        """
        level = 0
        current = self.parent
        while current:
            level += 1
            current = current.parent
        return level


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

        # 性能优化：为高频查询字段添加索引
        indexes = [
            models.Index(fields=['name'], name='process_name_idx'),
            models.Index(fields=['code'], name='process_code_idx'),
            models.Index(fields=['is_active'], name='process_is_active_idx'),
            models.Index(fields=['sort_order'], name='process_sort_order_idx'),
            models.Index(
                fields=['is_active', 'sort_order'],
                name='process_active_sort_idx'
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_required_plates(self):
        """获取工序需要的版列表

        Returns:
            list: 需要的版类型列表（如 ['artwork', 'die']）
        """
        required = []
        if self.requires_artwork:
            required.append('artwork')
        if self.requires_die:
            required.append('die')
        if self.requires_foiling_plate:
            required.append('foiling_plate')
        if self.requires_embossing_plate:
            required.append('embossing_plate')
        return required
