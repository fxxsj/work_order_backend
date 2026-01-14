"""
物料序列化器模块

包含物料、供应商、采购订单相关的序列化器。
"""

from rest_framework import serializers
from ..models.materials import Material, Supplier, MaterialSupplier, PurchaseOrder, PurchaseOrderItem


class MaterialSerializer(serializers.ModelSerializer):
    """物料序列化器"""
    class Meta:
        model = Material
        fields = '__all__'


class SupplierSerializer(serializers.ModelSerializer):
    """供应商序列化器"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    material_count = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = '__all__'

    def get_material_count(self, obj):
        """获取该供应商供应的物料数量"""
        return MaterialSupplier.objects.filter(supplier=obj).count()


class MaterialSupplierSerializer(serializers.ModelSerializer):
    """物料供应商关联序列化器"""
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    supplier_code = serializers.CharField(source='supplier.code', read_only=True)

    class Meta:
        model = MaterialSupplier
        fields = '__all__'
        read_only_fields = ['created_at']


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    """采购单明细序列化器"""
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    remaining_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class PurchaseOrderListSerializer(serializers.ModelSerializer):
    """采购单列表序列化器"""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    supplier_code = serializers.CharField(source='supplier.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    submitted_by_name = serializers.CharField(source='submitted_by.username', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, allow_null=True)
    work_order_number = serializers.CharField(source='work_order.order_number', read_only=True, allow_null=True)
    items_count = serializers.SerializerMethodField()
    received_progress = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = '__all__'

    def get_items_count(self, obj):
        """获取采购单明细数量"""
        return obj.items.count()

    def get_received_progress(self, obj):
        """获取收货进度"""
        items = obj.items.all()
        if not items:
            return 0
        total_quantity = sum(item.quantity for item in items)
        total_received = sum(item.received_quantity for item in items)
        if total_quantity == 0:
            return 0
        return round((total_received / total_quantity) * 100, 2)


class PurchaseOrderDetailSerializer(serializers.ModelSerializer):
    """采购单详情序列化器"""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    supplier_contact = serializers.CharField(source='supplier.contact_person', read_only=True)
    supplier_phone = serializers.CharField(source='supplier.phone', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    submitted_by_name = serializers.CharField(source='submitted_by.username', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, allow_null=True)
    work_order_number = serializers.CharField(source='work_order.order_number', read_only=True, allow_null=True)
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = '__all__'
        read_only_fields = ['order_number', 'total_amount', 'created_at', 'updated_at']
