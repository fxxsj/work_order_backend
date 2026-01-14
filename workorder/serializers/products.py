"""
产品序列化器模块

包含产品、产品物料、产品组相关的序列化器。
"""

from rest_framework import serializers
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
