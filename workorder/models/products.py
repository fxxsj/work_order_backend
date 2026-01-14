"""
产品相关模型

包含产品管理的相关模型：
- Product: 产品信息
- ProductGroup: 产品组
- ProductGroupItem: 产品组子项
- ProductMaterial: 产品默认物料配置
- ProductStockLog: 产品库存变更日志
"""

from django.db import models
from django.contrib.auth.models import User


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
        from .system import Notification
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
    material = models.ForeignKey('workorder.Material', on_delete=models.PROTECT, verbose_name='物料')
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
