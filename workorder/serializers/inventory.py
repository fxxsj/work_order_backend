"""
库存相关序列化器

包含库存管理的所有序列化器：
- ProductStock: 成品库存
- StockIn: 入库单
- StockOut: 出库单
- DeliveryOrder: 发货单
- DeliveryItem: 发货明细
- QualityInspection: 质量检验
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from workorder.models import (
    ProductStock, StockIn, StockOut,
    DeliveryOrder, DeliveryItem, QualityInspection
)


# ==================== 成品库存序列化器 ====================

class ProductStockSerializer(serializers.ModelSerializer):
    """成品库存序列化器"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    work_order_number = serializers.CharField(
        source='work_order.order_number', read_only=True, allow_null=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.SerializerMethodField()

    class Meta:
        model = ProductStock
        fields = '__all__'

    def get_days_until_expiry(self, obj):
        """获取距离过期的天数"""
        if obj.expiry_date:
            from django.utils import timezone
            delta = obj.expiry_date - timezone.now().date()
            return delta.days
        return None


class ProductStockUpdateSerializer(serializers.ModelSerializer):
    """成品库存更新序列化器"""

    class Meta:
        model = ProductStock
        fields = ['quantity', 'location', 'status', 'notes']


# ==================== 入库出库序列化器 ====================

class StockInSerializer(serializers.ModelSerializer):
    """入库单序列化器"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    work_order_number = serializers.CharField(
        source='work_order.order_number', read_only=True
    )
    operator_name = serializers.CharField(
        source='operator.username', read_only=True, allow_null=True
    )
    submitted_by_name = serializers.CharField(
        source='submitted_by.username', read_only=True, allow_null=True
    )
    approved_by_name = serializers.CharField(
        source='approved_by.username', read_only=True, allow_null=True
    )

    class Meta:
        model = StockIn
        fields = '__all__'
        read_only_fields = ['order_number']


class StockInCreateSerializer(serializers.ModelSerializer):
    """入库单创建序列化器"""

    class Meta:
        model = StockIn
        fields = ['work_order', 'stock_in_date', 'notes']

    def create(self, validated_data):
        """创建入库单"""
        work_order = validated_data.get('work_order')
        stock_in = StockIn.objects.create(**validated_data)

        # TODO: 自动创建ProductStock记录
        # 这里需要根据施工单的产品信息创建库存记录

        return stock_in


class StockOutSerializer(serializers.ModelSerializer):
    """出库单序列化器"""
    out_type_display = serializers.CharField(source='get_out_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    delivery_order_number = serializers.CharField(
        source='delivery_order.order_number', read_only=True, allow_null=True
    )
    operator_name = serializers.CharField(
        source='operator.username', read_only=True, allow_null=True
    )
    submitted_by_name = serializers.CharField(
        source='submitted_by.username', read_only=True, allow_null=True
    )
    approved_by_name = serializers.CharField(
        source='approved_by.username', read_only=True, allow_null=True
    )

    class Meta:
        model = StockOut
        fields = '__all__'
        read_only_fields = ['order_number']


# ==================== 发货管理序列化器 ====================

class DeliveryItemSerializer(serializers.ModelSerializer):
    """发货明细序列化器"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)

    class Meta:
        model = DeliveryItem
        fields = '__all__'

    def validate(self, data):
        """验证发货明细"""
        quantity = data.get('quantity')
        if quantity is not None and quantity <= 0:
            raise serializers.ValidationError({'quantity': '发货数量必须大于0'})
        return data


class DeliveryOrderSerializer(serializers.ModelSerializer):
    """发货单序列化器"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # 关联信息
    sales_order_number = serializers.CharField(
        source='sales_order.order_number', read_only=True
    )
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True
    )

    # 发货明细
    items = DeliveryItemSerializer(many=True, read_only=True)

    class Meta:
        model = DeliveryOrder
        fields = '__all__'
        read_only_fields = ['order_number']

    def get_items_count(self, obj):
        """获取发货明细数量"""
        return obj.items.count()


class DeliveryOrderListSerializer(serializers.ModelSerializer):
    """发货单列表序列化器（精简版）"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    sales_order_number = serializers.CharField(
        source='sales_order.order_number', read_only=True
    )
    items_count = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryOrder
        fields = [
            'id', 'order_number', 'customer_name', 'sales_order_number',
            'delivery_date', 'status', 'status_display', 'items_count',
            'total_quantity', 'logistics_company', 'tracking_number',
            'created_at'
        ]

    def get_items_count(self, obj):
        """获取发货明细数量"""
        return obj.items.count()

    def get_total_quantity(self, obj):
        """获取总发货数量"""
        return sum(item.quantity for item in obj.items.all())


class DeliveryOrderCreateSerializer(serializers.ModelSerializer):
    """发货单创建序列化器"""
    items_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='发货明细数据，格式：[{"product": id, "quantity": 1, "unit_price": 100}]'
    )

    class Meta:
        model = DeliveryOrder
        fields = [
            'sales_order', 'customer', 'delivery_date',
            'receiver_name', 'receiver_phone', 'delivery_address',
            'logistics_company', 'tracking_number', 'freight',
            'package_count', 'package_weight', 'notes', 'items_data'
        ]

    def validate(self, data):
        """验证创建数据"""
        # 必须选择客户和销售订单
        if not data.get('customer'):
            raise serializers.ValidationError({'customer': '必须选择客户'})
        if not data.get('sales_order'):
            raise serializers.ValidationError({'sales_order': '必须选择销售订单'})

        # 收货人信息必填
        if not data.get('receiver_name'):
            raise serializers.ValidationError({'receiver_name': '收货人不能为空'})
        if not data.get('receiver_phone'):
            raise serializers.ValidationError({'receiver_phone': '联系电话不能为空'})
        if not data.get('delivery_address'):
            raise serializers.ValidationError({'delivery_address': '送货地址不能为空'})

        return data

    def create(self, validated_data):
        """创建发货单"""
        items_data = validated_data.pop('items_data', [])
        delivery_order = DeliveryOrder.objects.create(**validated_data)

        # 创建发货明细
        for item_data in items_data:
            DeliveryItem.objects.create(
                delivery_order=delivery_order,
                **item_data
            )

        return delivery_order


class DeliveryOrderUpdateSerializer(serializers.ModelSerializer):
    """发货单更新序列化器"""
    items_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='发货明细数据'
    )

    class Meta:
        model = DeliveryOrder
        fields = [
            'delivery_date', 'status',
            'receiver_name', 'receiver_phone', 'delivery_address',
            'logistics_company', 'tracking_number', 'freight',
            'received_date', 'received_notes', 'receiver_signature',
            'package_count', 'package_weight', 'notes', 'items_data'
        ]

    def update(self, instance, validated_data):
        """更新发货单"""
        items_data = validated_data.pop('items_data', None)

        # 更新基本信息
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # 更新发货明细
        if items_data is not None:
            # 删除现有明细
            instance.items.all().delete()

            # 创建新明细
            for item_data in items_data:
                DeliveryItem.objects.create(
                    delivery_order=instance,
                    **item_data
                )

        return instance


# ==================== 质量检验序列化器 ====================

class QualityInspectionSerializer(serializers.ModelSerializer):
    """质量检验序列化器"""
    inspection_type_display = serializers.CharField(
        source='get_inspection_type_display', read_only=True
    )
    result_display = serializers.CharField(source='get_result_display', read_only=True)

    # 关联信息
    work_order_number = serializers.CharField(
        source='work_order.order_number', read_only=True, allow_null=True
    )
    product_name = serializers.CharField(
        source='product.name', read_only=True, allow_null=True
    )
    inspector_name = serializers.CharField(
        source='inspector.username', read_only=True, allow_null=True
    )

    # 格式化字段
    defective_rate_formatted = serializers.SerializerMethodField()

    class Meta:
        model = QualityInspection
        fields = '__all__'
        read_only_fields = ['inspection_number', 'defective_rate']

    def get_defective_rate_formatted(self, obj):
        """格式化不良率"""
        return f"{obj.defective_rate:.2f}%"


class QualityInspectionCreateSerializer(serializers.ModelSerializer):
    """质量检验创建序列化器"""

    class Meta:
        model = QualityInspection
        fields = [
            'inspection_type', 'work_order', 'product', 'batch_no',
            'inspection_date', 'inspector',
            'inspection_quantity', 'passed_quantity', 'failed_quantity',
            'inspection_standard', 'inspection_items',
            'defects', 'defect_description',
            'disposition', 'disposition_notes', 'notes'
        ]

    def validate(self, data):
        """验证创建数据"""
        inspection_quantity = data.get('inspection_quantity', 0)
        passed_quantity = data.get('passed_quantity', 0)
        failed_quantity = data.get('failed_quantity', 0)

        # 验证数量关系
        if failed_quantity > inspection_quantity:
            raise serializers.ValidationError({
                'failed_quantity': '不合格数量不能超过检验数量'
            })

        if passed_quantity + failed_quantity > inspection_quantity:
            raise serializers.ValidationError({
                'passed_quantity': '合格数量和不合格数量之和不能超过检验数量'
            })

        return data


class QualityInspectionUpdateSerializer(serializers.ModelSerializer):
    """质量检验更新序列化器"""

    class Meta:
        model = QualityInspection
        fields = [
            'result', 'inspection_quantity', 'passed_quantity', 'failed_quantity',
            'inspection_standard', 'inspection_items',
            'defects', 'defect_description',
            'disposition', 'disposition_notes', 'attachment', 'notes'
        ]


# ==================== 库存统计序列化器 ====================

class InventoryStatsSerializer(serializers.Serializer):
    """库存统计序列化器（用于报表）"""
    product_code = serializers.CharField()
    product_name = serializers.CharField()
    total_quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    available_quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    reserved_quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    defective_quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    locations = serializers.ListField(child=serializers.CharField())
    expired_count = serializers.IntegerField()
    expiring_soon_count = serializers.IntegerField()


class DeliveryStatsSerializer(serializers.Serializer):
    """发货统计序列化器（用于报表）"""
    period = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_freight = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_orders = serializers.IntegerField()
    shipped_orders = serializers.IntegerField()
    received_orders = serializers.IntegerField()
    on_time_delivery_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


# ==================== 导出所有序列化器 ====================

__all__ = [
    # 成品库存
    'ProductStockSerializer',
    'ProductStockUpdateSerializer',

    # 入库出库
    'StockInSerializer',
    'StockInCreateSerializer',
    'StockOutSerializer',

    # 发货管理
    'DeliveryItemSerializer',
    'DeliveryOrderSerializer',
    'DeliveryOrderListSerializer',
    'DeliveryOrderCreateSerializer',
    'DeliveryOrderUpdateSerializer',

    # 质量检验
    'QualityInspectionSerializer',
    'QualityInspectionCreateSerializer',
    'QualityInspectionUpdateSerializer',

    # 统计报表
    'InventoryStatsSerializer',
    'DeliveryStatsSerializer',
]
