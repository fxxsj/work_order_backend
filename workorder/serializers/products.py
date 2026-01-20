"""
产品序列化器模块

包含产品、产品物料、产品组相关的序列化器。
"""

from rest_framework import serializers
import re
from ..models.products import Product, ProductMaterial, ProductGroup, ProductGroupItem


class ProductMaterialSerializer(serializers.ModelSerializer):
    """产品物料序列化器"""
    material_name = serializers.SerializerMethodField()
    material_code = serializers.SerializerMethodField()

    class Meta:
        model = ProductMaterial
        fields = '__all__'

    def get_material_name(self, obj):
        return obj.material.name if obj.material else None

    def get_material_code(self, obj):
        return obj.material.code if obj.material else None


class ProductSerializer(serializers.ModelSerializer):
    """产品序列化器"""
    default_materials = ProductMaterialSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = '__all__'

    def validate_code(self, value):
        """验证产品编码格式"""
        if not value:
            raise serializers.ValidationError("产品编码不能为空")

        # 验证编码格式：只能包含字母、数字和连字符
        if not re.match(r'^[A-Za-z0-9-]+$', value):
            raise serializers.ValidationError("产品编码只能包含字母、数字和连字符")

        # 验证长度
        if len(value) < 2:
            raise serializers.ValidationError("产品编码至少需要2个字符")

        if len(value) > 50:
            raise serializers.ValidationError("产品编码不能超过50个字符")

        return value

    def validate_name(self, value):
        """验证产品名称"""
        if not value or not value.strip():
            raise serializers.ValidationError("产品名称不能为空")

        if len(value) > 200:
            raise serializers.ValidationError("产品名称不能超过200个字符")

        return value.strip()

    def validate_unit_price(self, value):
        """验证单价"""
        if value < 0:
            raise serializers.ValidationError("单价不能为负数")

        # 验证精度（最大10位数字，2位小数）
        if value > 99999999.99:
            raise serializers.ValidationError("单价超出允许范围")

        return value

    def validate_stock_quantity(self, value):
        """验证库存数量"""
        if value < 0:
            raise serializers.ValidationError("库存数量不能为负数")

        return value

    def validate_min_stock_quantity(self, value):
        """验证最小库存"""
        if value < 0:
            raise serializers.ValidationError("最小库存不能为负数")

        return value

    def validate(self, attrs):
        """对象级验证"""
        stock_quantity = attrs.get('stock_quantity', 0)
        min_stock_quantity = attrs.get('min_stock_quantity', 0)

        # 验证最小库存不能大于库存数量（仅在有明确库存值时验证）
        # 创建时可以设置初始库存和预警值，但如果库存已存在则不能违反业务规则
        if self.instance and min_stock_quantity > stock_quantity:
            raise serializers.ValidationError({
                'min_stock_quantity': '最小库存不能大于当前库存数量'
            })

        return attrs


class ProductGroupItemSerializer(serializers.ModelSerializer):
    """产品组子项序列化器"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_group_name = serializers.CharField(source='product_group.name', read_only=True)
    product_group_code = serializers.CharField(source='product_group.code', read_only=True)

    class Meta:
        model = ProductGroupItem
        fields = '__all__'


class ProductGroupSerializer(serializers.ModelSerializer):
    """产品组序列化器"""
    items = ProductGroupItemSerializer(many=True, read_only=True)

    class Meta:
        model = ProductGroup
        fields = '__all__'
