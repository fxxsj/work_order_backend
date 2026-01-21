"""
物料序列化器模块

包含物料、供应商、采购订单相关的序列化器。
"""

import re
from rest_framework import serializers
from ..models.materials import Material, Supplier, MaterialSupplier, PurchaseOrder, PurchaseOrderItem


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

    class Meta:
        model = PurchaseOrder
        fields = '__all__'
        read_only_fields = ['order_number', 'total_amount', 'created_at', 'updated_at']
