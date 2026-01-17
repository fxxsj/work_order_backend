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

    def validate(self, attrs):
        """验证订单明细数据"""
        import sys
        print(f"[DEBUG] Validating SalesOrderItem: {attrs}", file=sys.stderr)
        return attrs

    def create(self, validated_data):
        """创建订单明细"""
        import sys
        print(f"[DEBUG] Creating SalesOrderItem with data: {validated_data}", file=sys.stderr)
        return super().create(validated_data)


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

    def create(self, validated_data):
        """创建销售订单及其明细"""
        items_data = validated_data.pop('items', [])
        
        # 打印调试信息
        import sys
        print(f"[DEBUG] Creating sales order with data:", validated_data, file=sys.stderr)
        print(f"[DEBUG] Items data:", items_data, file=sys.stderr)
        
        try:
            sales_order = SalesOrder.objects.create(**validated_data)
            print(f"[DEBUG] SalesOrder created successfully with ID: {sales_order.id}", file=sys.stderr)
        except Exception as e:
            print(f"[DEBUG] Failed to create SalesOrder: {str(e)}", file=sys.stderr)
            raise serializers.ValidationError(f'创建销售订单失败: {str(e)}')
        
        # 创建订单明细
        for i, item_data in enumerate(items_data):
            try:
                print(f"[DEBUG] Creating item {i+1} with data: {item_data}", file=sys.stderr)
                SalesOrderItem.objects.create(sales_order=sales_order, **item_data)
                print(f"[DEBUG] Item {i+1} created successfully", file=sys.stderr)
            except Exception as e:
                print(f"[DEBUG] Failed to create item {i+1}: {str(e)}", file=sys.stderr)
                raise serializers.ValidationError(f'创建订单明细失败 (第{i+1}项): {str(e)}')
        
        # 更新订单总金额
        try:
            sales_order.update_totals()
            print(f"[DEBUG] Totals updated successfully", file=sys.stderr)
        except Exception as e:
            print(f"[DEBUG] Failed to update totals: {str(e)}", file=sys.stderr)
            # 不阻止流程，记录错误即可
        
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
