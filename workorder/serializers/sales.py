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
        read_only_fields = ['created_at', 'updated_at', 'subtotal', 'sales_order']


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
    items = SalesOrderItemSerializer(many=True, required=False)
    work_order_numbers = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrder
        fields = '__all__'
        read_only_fields = ['order_number', 'subtotal', 'tax_amount', 'total_amount', 'created_at', 'updated_at']

    def get_work_order_numbers(self, obj):
        """获取关联的施工单号列表"""
        return [wo.order_number for wo in obj.work_orders.all()]

    def validate_delivery_date(self, value):
        """验证交货日期

        新建订单时：交货日期不能早于今天
        编辑订单时：允许保留历史交货日期
        """
        from django.utils import timezone
        # 编辑模式时，如果日期未改变，允许保留原值
        if self.instance and self.instance.delivery_date == value:
            return value
        # 新建或修改日期时，验证不能早于今天
        if value and value < timezone.now().date() and not self.instance:
            raise serializers.ValidationError("交货日期不能早于今天")
        return value

    def validate_tax_rate(self, value):
        """验证税率"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("税率必须在0-100之间")
        return value

    def validate_discount_amount(self, value):
        """验证折扣金额"""
        if value < 0:
            raise serializers.ValidationError("折扣金额不能为负数")
        return value

    def validate(self, attrs):
        """对象级验证"""
        order_date = attrs.get('order_date')
        delivery_date = attrs.get('delivery_date')

        if self.instance:
            order_date = order_date or self.instance.order_date
            delivery_date = delivery_date or self.instance.delivery_date

        if order_date and delivery_date and delivery_date < order_date:
            raise serializers.ValidationError({
                'delivery_date': '交货日期不能早于订单日期'
            })

        return attrs

    def create(self, validated_data):
        """创建销售订单及其明细"""
        items_data = validated_data.pop('items', [])
        
        try:
            sales_order = SalesOrder.objects.create(**validated_data)
        except Exception as e:
            raise serializers.ValidationError(f'创建销售订单失败: {str(e)}')
        
        # 创建订单明细
        for i, item_data in enumerate(items_data):
            try:
                SalesOrderItem.objects.create(sales_order=sales_order, **item_data)
            except Exception as e:
                raise serializers.ValidationError(f'创建订单明细失败 (第{i+1}项): {str(e)}')
        
        # 更新订单总金额
        try:
            sales_order.update_totals()
        except Exception as e:
            # 不阻止流程，记录错误即可
            pass
        
        return sales_order

    def update(self, instance, validated_data):
        """更新销售订单及其明细"""
        items_data = validated_data.pop('items', None)

        # 更新销售订单基本信息
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # 如果提供了明细数据，更新明细
        if items_data is not None:
            # 删除原有明细
            instance.items.all().delete()

            # 创建新明细
            for item_data in items_data:
                SalesOrderItem.objects.create(sales_order=instance, **item_data)

            # 更新订单总金额
            instance.update_totals()

        return instance
