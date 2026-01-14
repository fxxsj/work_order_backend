"""
销售订单序列化器模块

包含销售订单和销售订单明细的序列化器。
"""

from rest_framework import serializers
from ..models.sales import SalesOrder, SalesOrderItem


class SalesOrderItemSerializer(serializers.ModelSerializer):
    """销售订单明细序列化器"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SalesOrderItem
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'subtotal']


class SalesOrderListSerializer(serializers.ModelSerializer):
    """销售订单列表序列化器"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_code = serializers.CharField(source='customer.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    submitted_by_name = serializers.CharField(source='submitted_by.username', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, allow_null=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrder
        fields = '__all__'

    def get_items_count(self, obj):
        """获取订单明细数量"""
        return obj.items.count()


class SalesOrderDetailSerializer(serializers.ModelSerializer):
    """销售订单详情序列化器"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_contact = serializers.CharField(source='customer.contact_person', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    customer_address = serializers.CharField(source='customer.address', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    submitted_by_name = serializers.CharField(source='submitted_by.username', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, allow_null=True)
    items = SalesOrderItemSerializer(many=True, read_only=True)
    work_order_numbers = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrder
        fields = '__all__'
        read_only_fields = ['order_number', 'subtotal', 'tax_amount', 'total_amount', 'created_at', 'updated_at']

    def get_work_order_numbers(self, obj):
        """获取关联的施工单号列表"""
        return [wo.order_number for wo in obj.work_orders.all()]
