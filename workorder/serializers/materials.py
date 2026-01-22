"""
物料序列化器模块

包含物料、供应商、采购订单相关的序列化器。
"""

import re
from rest_framework import serializers
from ..models.materials import (
    Material, Supplier, MaterialSupplier,
    PurchaseOrder, PurchaseOrderItem, PurchaseReceiveRecord
)


class MaterialSerializer(serializers.ModelSerializer):
    """物料序列化器（增强版）"""

    class Meta:
        model = Material
        fields = '__all__'

    def validate_code(self, value):
        """验证物料编码格式"""
        if not value:
            raise serializers.ValidationError("物料编码不能为空")

        if not re.match(r'^[A-Za-z0-9-]+$', value):
            raise serializers.ValidationError("物料编码只能包含字母、数字和连字符")

        if len(value) < 2 or len(value) > 50:
            raise serializers.ValidationError("物料编码长度必须在2-50个字符之间")

        return value

    def validate_name(self, value):
        """验证物料名称"""
        if not value or not value.strip():
            raise serializers.ValidationError("物料名称不能为空")

        if len(value) > 200:
            raise serializers.ValidationError("物料名称不能超过200个字符")

        return value.strip()

    def validate_unit_price(self, value):
        """验证单价"""
        if value < 0:
            raise serializers.ValidationError("单价不能为负数")

        if value > 999999999.99:
            raise serializers.ValidationError("单价超出允许范围（最大999999999.99）")

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

    def validate_unit(self, value):
        """验证单位"""
        if not value or not value.strip():
            raise serializers.ValidationError("单位不能为空")
        return value.strip()

    def validate_lead_time_days(self, value):
        """验证采购周期"""
        if value < 0:
            raise serializers.ValidationError("采购周期不能为负数")

        if value > 365:
            raise serializers.ValidationError("采购周期不能超过365天")

        return value

    def validate(self, attrs):
        """对象级业务规则验证"""
        stock_quantity = attrs.get('stock_quantity', 0)
        min_stock_quantity = attrs.get('min_stock_quantity', 0)

        # 编辑模式：最小库存不能大于当前库存
        if self.instance and min_stock_quantity > stock_quantity:
            raise serializers.ValidationError({
                'min_stock_quantity': '最小库存不能大于当前库存数量'
            })

        # 验证默认供应商关联
        default_supplier = attrs.get('default_supplier')
        if default_supplier:
            if hasattr(default_supplier, 'status') and default_supplier.status != 'active':
                raise serializers.ValidationError({
                    'default_supplier': '选择的供应商已停用，请选择其他供应商或联系管理员'
                })

        return attrs


class SupplierSerializer(serializers.ModelSerializer):
    """供应商序列化器（优化版）"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    material_count = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = '__all__'

    def get_material_count(self, obj):
        """获取该供应商供应的物料数量（优化版：使用注解）"""
        # 使用预加载的注解字段，避免N+1查询
        if hasattr(obj, '_material_count'):
            return obj._material_count
        # 回退方案：新创建的对象没有注解，使用直接查询
        return obj.materialsupplier_set.count()

    def validate_code(self, value):
        """验证供应商编码格式"""
        if not value:
            raise serializers.ValidationError("供应商编码不能为空")

        # 支持字母、数字、连字符和中文字符
        if not re.match(r'^[\u4e00-\u9fa5A-Za-z0-9-]+$', value):
            raise serializers.ValidationError("供应商编码只能包含中文、字母、数字和连字符")

        if len(value) < 2 or len(value) > 50:
            raise serializers.ValidationError("供应商编码长度必须在2-50个字符之间")

        return value

    def validate_name(self, value):
        """验证供应商名称"""
        if not value or not value.strip():
            raise serializers.ValidationError("供应商名称不能为空")

        if len(value) > 200:
            raise serializers.ValidationError("供应商名称不能超过200个字符")

        return value.strip()

    def validate_phone(self, value):
        """验证手机号格式（可选字段）"""
        if value:
            # 支持手机号和座机号
            phone_pattern = r'^(1[3-9]\d{9}|0\d{2,3}-?\d{7,8})$'
            if not re.match(phone_pattern, value):
                raise serializers.ValidationError("请输入正确的联系电话（手机号或座机号）")
        return value

    def validate_email(self, value):
        """验证邮箱格式（可选字段）"""
        if value:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, value):
                raise serializers.ValidationError("请输入正确的邮箱地址")
        return value


class MaterialSupplierSerializer(serializers.ModelSerializer):
    """物料供应商关联序列化器（增强版）"""
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    supplier_code = serializers.CharField(source='supplier.code', read_only=True)

    class Meta:
        model = MaterialSupplier
        fields = '__all__'
        read_only_fields = ['created_at']

    def validate_supplier_price(self, value):
        """验证供应商价格"""
        if value < 0:
            raise serializers.ValidationError("供应商价格不能为负数")

        if value > 999999999.99:
            raise serializers.ValidationError("供应商价格超出允许范围")

        return value

    def validate_min_order_quantity(self, value):
        """验证最小起订量"""
        if value <= 0:
            raise serializers.ValidationError("最小起订量必须大于0")
        return value

    def validate_lead_time_days(self, value):
        """验证采购周期"""
        if value < 0:
            raise serializers.ValidationError("采购周期不能为负数")

        if value > 365:
            raise serializers.ValidationError("采购周期不能超过365天")

        return value

    def validate(self, attrs):
        """验证物料-供应商唯一性"""
        material = attrs.get('material')
        supplier = attrs.get('supplier')

        # 创建时检查唯一性
        if not self.instance and material and supplier:
            if MaterialSupplier.objects.filter(material=material, supplier=supplier).exists():
                raise serializers.ValidationError({
                    'non_field_errors': '该物料已关联此供应商'
                })

        # 更新时检查唯一性（排除自身）
        if self.instance and material and supplier:
            if MaterialSupplier.objects.filter(
                material=material,
                supplier=supplier
            ).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError({
                    'non_field_errors': '该物料已关联此供应商'
                })

        return attrs


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    """采购单明细序列化器（增强版）"""
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    remaining_quantity = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate_quantity(self, value):
        """验证采购数量"""
        if value <= 0:
            raise serializers.ValidationError("采购数量必须大于0")
        return value

    def validate_unit_price(self, value):
        """验证单价"""
        if value < 0:
            raise serializers.ValidationError("单价不能为负数")

        if value > 999999999.99:
            raise serializers.ValidationError("单价超出允许范围")

        return value

    def validate_received_quantity(self, value):
        """验证已收货数量"""
        if value < 0:
            raise serializers.ValidationError("已收货数量不能为负数")

        # 收货数量不能超过采购数量
        if self.instance and value > self.instance.quantity:
            raise serializers.ValidationError("已收货数量不能超过采购数量")

        return value

    def validate(self, attrs):
        """对象级验证"""
        quantity = attrs.get('quantity')
        received_quantity = attrs.get('received_quantity', 0)

        # 验证收货数量
        if quantity and received_quantity > quantity:
            raise serializers.ValidationError({
                'received_quantity': '已收货数量不能超过采购数量'
            })

        return attrs


class PurchaseOrderListSerializer(serializers.ModelSerializer):
    """采购单列表序列化器（优化版）"""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    supplier_code = serializers.CharField(source='supplier.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    submitted_by_name = serializers.CharField(source='submitted_by.username', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, allow_null=True)
    work_order_number = serializers.CharField(source='work_order.order_number', read_only=True, allow_null=True)

    # 优化：使用注解字段，避免N+1查询
    items_count = serializers.IntegerField(read_only=True)
    received_progress = serializers.FloatField(read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = '__all__'


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

    # 用于创建/更新时接收 items 数据
    items_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = PurchaseOrder
        fields = '__all__'
        read_only_fields = ['order_number', 'total_amount', 'created_at', 'updated_at']

    def create(self, validated_data):
        """创建采购单及其明细"""
        items_data = validated_data.pop('items_data', [])

        # 创建采购单
        purchase_order = PurchaseOrder.objects.create(**validated_data)

        # 创建明细
        for item_data in items_data:
            PurchaseOrderItem.objects.create(
                purchase_order=purchase_order,
                material_id=item_data.get('material'),
                quantity=item_data.get('quantity', 0),
                unit_price=item_data.get('unit_price', 0)
            )

        # 更新总金额
        purchase_order.update_total_amount()

        return purchase_order

    def update(self, instance, validated_data):
        """更新采购单及其明细"""
        items_data = validated_data.pop('items_data', None)

        # 更新采购单基本信息
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # 如果提供了 items_data，更新明细
        if items_data is not None:
            # 删除旧的明细
            instance.items.all().delete()

            # 创建新的明细
            for item_data in items_data:
                PurchaseOrderItem.objects.create(
                    purchase_order=instance,
                    material_id=item_data.get('material'),
                    quantity=item_data.get('quantity', 0),
                    unit_price=item_data.get('unit_price', 0)
                )

            # 更新总金额
            instance.update_total_amount()

        return instance


# ========== 收货记录序列化器 ==========

class PurchaseReceiveRecordSerializer(serializers.ModelSerializer):
    """采购收货记录序列化器"""
    # 关联信息（只读）
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_unit = serializers.CharField(source='material.unit', read_only=True)
    purchase_order_number = serializers.CharField(
        source='purchase_order.order_number', read_only=True
    )
    inspection_status_display = serializers.CharField(
        source='get_inspection_status_display', read_only=True
    )

    # 操作人信息（只读）
    received_by_name = serializers.CharField(
        source='received_by.username', read_only=True, allow_null=True
    )
    inspected_by_name = serializers.CharField(
        source='inspected_by.username', read_only=True, allow_null=True
    )
    stocked_by_name = serializers.CharField(
        source='stocked_by.username', read_only=True, allow_null=True
    )
    returned_by_name = serializers.CharField(
        source='returned_by.username', read_only=True, allow_null=True
    )

    class Meta:
        model = PurchaseReceiveRecord
        fields = '__all__'
        read_only_fields = [
            'created_at', 'updated_at',
            'inspected_at', 'stocked_at', 'returned_at',
            'is_stocked', 'is_returned'
        ]

    def validate_received_quantity(self, value):
        """验证收货数量"""
        if value <= 0:
            raise serializers.ValidationError("收货数量必须大于0")
        return value

    def validate(self, attrs):
        """对象级验证"""
        item = attrs.get('purchase_order_item')

        if item:
            # 验证采购单状态
            if item.purchase_order.status != 'ordered':
                raise serializers.ValidationError({
                    'purchase_order_item': '只有已下单状态的采购单才能收货'
                })

            # 验证收货数量不能超过剩余数量
            received_qty = attrs.get('received_quantity', 0)
            # 计算已收货的数量（来自收货记录）
            existing_received = sum(
                r.received_quantity or 0
                for r in item.receive_records.all()
            )
            remaining = item.quantity - existing_received

            if received_qty > remaining:
                raise serializers.ValidationError({
                    'received_quantity': f'收货数量不能超过剩余数量 {remaining}'
                })

        return attrs


class PurchaseReceiveRecordCreateSerializer(serializers.Serializer):
    """批量创建收货记录的序列化器"""
    items = serializers.ListField(
        child=serializers.DictField(),
        help_text='收货明细列表，每项包含 item_id, received_quantity, delivery_note_number, notes'
    )
    received_date = serializers.DateField(
        required=False,
        help_text='收货日期，默认为今天'
    )

    def validate_items(self, value):
        """验证收货明细"""
        if not value:
            raise serializers.ValidationError("收货明细不能为空")

        for item in value:
            if 'item_id' not in item:
                raise serializers.ValidationError("每个收货明细必须包含 item_id")
            if 'received_quantity' not in item:
                raise serializers.ValidationError("每个收货明细必须包含 received_quantity")
            if item['received_quantity'] <= 0:
                raise serializers.ValidationError("收货数量必须大于0")

        return value


class InspectionConfirmSerializer(serializers.Serializer):
    """质检确认序列化器"""
    qualified_quantity = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='合格数量'
    )
    unqualified_quantity = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        default=0,
        help_text='不合格数量'
    )
    unqualified_reason = serializers.CharField(
        required=False, allow_blank=True,
        help_text='不合格原因'
    )

    def validate(self, attrs):
        """验证合格数量和不合格数量"""
        qualified = attrs.get('qualified_quantity', 0)
        unqualified = attrs.get('unqualified_quantity', 0)

        if qualified < 0:
            raise serializers.ValidationError({
                'qualified_quantity': '合格数量不能为负数'
            })

        if unqualified < 0:
            raise serializers.ValidationError({
                'unqualified_quantity': '不合格数量不能为负数'
            })

        # 如果有不合格数量，必须填写原因
        if unqualified > 0 and not attrs.get('unqualified_reason'):
            raise serializers.ValidationError({
                'unqualified_reason': '存在不合格物料时必须填写不合格原因'
            })

        return attrs


class ReturnProcessSerializer(serializers.Serializer):
    """退货处理序列化器"""
    return_quantity = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='退货数量'
    )
    return_note = serializers.CharField(
        required=False, allow_blank=True,
        help_text='退货备注'
    )

    def validate_return_quantity(self, value):
        """验证退货数量"""
        if value <= 0:
            raise serializers.ValidationError("退货数量必须大于0")
        return value
