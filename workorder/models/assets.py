"""
资产相关模型

包含资产管理相关模型：
- Artwork: 图稿信息
- ArtworkProduct: 图稿产品关联
- Die: 刀模信息
- DieProduct: 刀模产品关联
- FoilingPlate: 烫金版信息
- FoilingPlateProduct: 烫金版产品关联
- EmbossingPlate: 压凸版信息
- EmbossingPlateProduct: 压凸版产品关联
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from django.db.models import Max


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

        # 性能优化：为高频查询字段添加索引
        indexes = [
            models.Index(fields=['name'], name='artwork_name_idx'),
            models.Index(fields=['confirmed'], name='artwork_confirmed_idx'),
            models.Index(fields=['created_at'], name='artwork_created_idx'),
        ]

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
    product = models.ForeignKey('workorder.Product', on_delete=models.PROTECT, verbose_name='产品')
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
    code = models.CharField('刀模编码', max_length=50, unique=True, blank=True,
                           help_text='刀模唯一编码，留空则自动生成，格式：DIE + yyyymm + 3位序号')
    name = models.CharField('刀模名称', max_length=200,
                           help_text='刀模的描述性名称，必填，最大200字符')
    size = models.CharField('尺寸', max_length=100, blank=True,
                           help_text='刀模尺寸规格，如：420x594mm、889x1194mm等')
    material = models.CharField('材质', max_length=100, blank=True,
                               help_text='刀模材质，如：木板、胶板、钢板等')
    thickness = models.CharField('厚度', max_length=50, blank=True,
                                help_text='刀模厚度，如：3mm、5mm等')
    # 刀模确认相关字段
    confirmed = models.BooleanField('已确认', default=False,
                                   help_text='设计部是否已确认该刀模，确认后关键字段不可修改')
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='confirmed_dies', verbose_name='确认人',
                                     help_text='确认该刀模的用户')
    confirmed_at = models.DateTimeField('确认时间', null=True, blank=True,
                                        help_text='刀模被确认的时间')
    notes = models.TextField('备注', blank=True,
                            help_text='刀模的补充说明信息')
    created_at = models.DateTimeField('创建时间', auto_now_add=True,
                                      help_text='刀模记录创建时间')
    updated_at = models.DateTimeField('更新时间', auto_now=True,
                                      help_text='刀模记录最后更新时间')

    class Meta:
        verbose_name = '刀模'
        verbose_name_plural = '刀模管理'
        ordering = ['-created_at']

        # 性能优化：为高频查询字段添加索引
        indexes = [
            models.Index(fields=['code'], name='die_code_idx'),
            models.Index(fields=['name'], name='die_name_idx'),
            models.Index(fields=['confirmed'], name='die_confirmed_idx'),
            models.Index(fields=['created_at'], name='die_created_idx'),
        ]

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
    product = models.ForeignKey('workorder.Product', on_delete=models.PROTECT, verbose_name='产品')
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

        # 性能优化：为高频查询字段添加索引
        indexes = [
            models.Index(fields=['code'], name='foiling_plate_code_idx'),
            models.Index(fields=['name'], name='foiling_plate_name_idx'),
            models.Index(fields=['confirmed'], name='foiling_plate_confirmed_idx'),
            models.Index(fields=['created_at'], name='foiling_plate_created_idx'),
        ]

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
    product = models.ForeignKey('workorder.Product', on_delete=models.PROTECT, verbose_name='产品')
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

        # 性能优化：为高频查询字段添加索引
        indexes = [
            models.Index(fields=['code'], name='embossing_plate_code_idx'),
            models.Index(fields=['name'], name='embossing_plate_name_idx'),
            models.Index(fields=['confirmed'], name='embossing_plate_conf_idx'),
            models.Index(fields=['created_at'], name='embossing_plate_created_idx'),
        ]

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
    product = models.ForeignKey('workorder.Product', on_delete=models.PROTECT, verbose_name='产品')
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
