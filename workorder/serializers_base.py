"""
基础序列化器

提供通用的序列化器基类和混入类，减少代码重复
"""

from rest_framework import serializers
from rest_framework.fields import Field


class BasePlateSerializer(serializers.ModelSerializer):
    """
    版（Die/FoilingPlate/EmbossingPlate）序列化器基类

    为 Die, FoilingPlate, EmbossingPlate 提供通用的序列化逻辑
    """

    class Meta:
        abstract = True

    def to_representation(self, instance):
        """自定义输出格式"""
        data = super().to_representation(instance)

        # 通用字段处理
        if hasattr(instance, 'confirmed'):
            data['status_display'] = '已确认' if instance.confirmed else '未确认'

        return data

    def validate(self, attrs):
        """通用验证逻辑"""
        # 如果有 version 字段，确保版本号是正整数
        if 'version' in attrs and attrs['version'] and attrs['version'] < 1:
            raise serializers.ValidationError({'version': '版本号必须大于0'})

        return super().validate(attrs)


class BaseProductSerializer(serializers.ModelSerializer):
    """
    产品序列化器基类

    为 Product 相关序列化器提供通用逻辑
    """

    class Meta:
        abstract = True

    def get_stock_status(self, obj):
        """获取库存状态"""
        if not hasattr(obj, 'current_stock'):
            return None

        min_stock = getattr(obj, 'min_stock', 0)

        if obj.current_stock <= 0:
            return 'out_of_stock'
        elif obj.current_stock < min_stock:
            return 'low_stock'
        else:
            return 'in_stock'


class TimestampMixin(serializers.ModelSerializer):
    """
    时间戳混入类

    自动包含创建时间和更新时间字段
    """

    class Meta:
        abstract = True
        fields = ('created_at', 'updated_at')


class UserStampedMixin(serializers.ModelSerializer):
    """
    用户标记混入类

    自动包含创建者和更新者字段
    """

    class Meta:
        abstract = True
        fields = ('created_by', 'updated_by')


class ReadOnlyFieldsMixin(serializers.ModelSerializer):
    """
    只读字段混入类

    指定某些字段在序列化时只读
    """

    # 子类需要定义 readonly_fields
    readonly_fields = []

    def get_fields(self):
        fields = super().get_fields()

        for field_name in self.readonly_fields:
            if field_name in fields:
                fields[field_name].read_only = True

        return fields


class DynamicFieldsMixin(serializers.ModelSerializer):
    """
    动态字段混入类

    根据用户权限动态返回字段
    """

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')

        if not request or not request.user:
            return fields

        # 示例：非管理员用户不看到价格字段
        if not request.user.is_superuser:
            fields.pop('unit_price', None)
            fields.pop('total_price', None)

        return fields


class PrefetchMixin(serializers.ModelSerializer):
    """
    预加载混入类

    优化关联对象的查询，避免 N+1 问题
    """

    @classmethod
    def setup_eager_loading(cls, queryset):
        """
        设置预加载

        使用:
        queryset = Model.objects.all()
        queryset = MySerializer.setup_eager_loading(queryset)
        """
        # 子类应该重写这个方法来定义预加载逻辑
        return queryset


class ValidationMixin(serializers.ModelSerializer):
    """
    验证混入类

    提供通用的验证方法
    """

    def validate_positive(self, value, field_name):
        """验证正数"""
        if value is not None and value < 0:
            raise serializers.ValidationError({field_name: f'{field_name} 不能为负数'})
        return value

    def validate_required(self, value, field_name):
        """验证必填"""
        if value is None or value == '':
            raise serializers.ValidationError({field_name: f'{field_name} 不能为空'})
        return value

    def validate_date_range(self, start_date, end_date, field_name_prefix=''):
        """验证日期范围"""
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({
                field_name_prefix + 'start_date': '开始日期不能晚于结束日期'
            })
        return start_date, end_date


# 通用字段
class HumanReadableBooleanField(Field):
    """
    人类可读的布尔值字段

    将 True/False 转换为"是"/"否"
    """

    def to_representation(self, value):
        if value is True:
            return "是"
        elif value is False:
            return "否"
        return None


class ChoiceFieldDisplayName(serializers.ChoiceField):
    """
    带显示名称的选择字段

    自动使用模型的 get_FOO_display() 方法
    """

    def __init__(self, **kwargs):
        kwargs['read_only'] = True
        super().__init__(**kwargs)

    def to_representation(self, value):
        if hasattr(value, 'get_{}_display'.format(self.field_name)):
            return getattr(value, 'get_{}_display'.format(self.field_name))()
        return super().to_representation(value)
