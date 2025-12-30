from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Customer, Department, Process, Product, ProductMaterial, Material, WorkOrder,
    WorkOrderProcess, WorkOrderMaterial, WorkOrderProduct, ProcessLog, Artwork, ArtworkProduct,
    Die, DieProduct, WorkOrderTask, ProductGroup, ProductGroupItem
)


class UserSerializer(serializers.ModelSerializer):
    """用户序列化器"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


class CustomerSerializer(serializers.ModelSerializer):
    """客户序列化器"""
    class Meta:
        model = Customer
        fields = '__all__'


class DepartmentSerializer(serializers.ModelSerializer):
    """部门序列化器"""
    class Meta:
        model = Department
        fields = '__all__'


class ProcessSerializer(serializers.ModelSerializer):
    """工序序列化器"""
    class Meta:
        model = Process
        fields = '__all__'


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


class MaterialSerializer(serializers.ModelSerializer):
    """物料序列化器"""
    class Meta:
        model = Material
        fields = '__all__'


class ProcessLogSerializer(serializers.ModelSerializer):
    """工序日志序列化器"""
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)
    
    class Meta:
        model = ProcessLog
        fields = '__all__'


class WorkOrderTaskSerializer(serializers.ModelSerializer):
    """施工单任务序列化器"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = WorkOrderTask
        fields = '__all__'


class WorkOrderProcessSerializer(serializers.ModelSerializer):
    """施工单工序序列化器"""
    process_name = serializers.CharField(source='process.name', read_only=True)
    process_code = serializers.CharField(source='process.code', read_only=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)
    department_code = serializers.CharField(source='department.code', read_only=True, allow_null=True)
    logs = ProcessLogSerializer(many=True, read_only=True)
    tasks = WorkOrderTaskSerializer(many=True, read_only=True)
    
    class Meta:
        model = WorkOrderProcess
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


class WorkOrderProductSerializer(serializers.ModelSerializer):
    """施工单产品序列化器"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_detail = ProductSerializer(source='product', read_only=True)
    
    class Meta:
        model = WorkOrderProduct
        fields = '__all__'


class WorkOrderMaterialSerializer(serializers.ModelSerializer):
    """施工单物料序列化器"""
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_unit = serializers.CharField(source='material.unit', read_only=True)
    purchase_status_display = serializers.CharField(source='get_purchase_status_display', read_only=True)
    
    class Meta:
        model = WorkOrderMaterial
        fields = '__all__'


class WorkOrderListSerializer(serializers.ModelSerializer):
    """施工单列表序列化器（精简版）"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True, allow_null=True)
    manager_name = serializers.CharField(source='manager.username', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    # 多产品合并显示字段
    product_name = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkOrder
        fields = [
            'id', 'order_number', 'customer', 'customer_name',
            'product', 'product_code', 'product_name', 'quantity', 'unit', 'status', 'status_display',
            'priority', 'priority_display', 'order_date', 'delivery_date',
            'total_amount', 'manager', 'manager_name', 'progress_percentage',
            'created_at'
        ]
    
    def get_progress_percentage(self, obj):
        return obj.get_progress_percentage()
    
    def get_product_name(self, obj):
        """如果有多个产品，显示为 'xx款拼版'，否则显示单个产品名称"""
        products = obj.products.all()
        if products.count() > 1:
            return f'{products.count()}款拼版'
        elif products.count() == 1:
            return products.first().product_name
        else:
            # 如果没有关联产品，使用旧的单个产品字段
            return obj.product_name
    
    def get_quantity(self, obj):
        """如果有多个产品，返回所有产品的数量总和"""
        products = obj.products.all()
        if products.count() > 0:
            return sum(p.quantity for p in products)
        else:
            # 如果没有关联产品，使用旧的单个产品数量
            return obj.quantity or 0
    
    def get_unit(self, obj):
        """如果有多个产品，返回第一个产品的单位"""
        products = obj.products.all()
        if products.count() > 0:
            return products.first().unit
        else:
            # 如果没有关联产品，使用旧的单个产品单位
            return obj.unit or '件'


class WorkOrderDetailSerializer(serializers.ModelSerializer):
    """施工单详情序列化器（完整版）"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_detail = CustomerSerializer(source='customer', read_only=True)
    product_detail = ProductSerializer(source='product', read_only=True)
    manager_name = serializers.CharField(source='manager.username', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    artwork_name = serializers.CharField(source='artwork.name', read_only=True, allow_null=True)
    artwork_code = serializers.CharField(source='artwork.code', read_only=True, allow_null=True)
    die_name = serializers.CharField(source='die.name', read_only=True, allow_null=True)
    die_code = serializers.CharField(source='die.code', read_only=True, allow_null=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    
    order_processes = WorkOrderProcessSerializer(many=True, read_only=True)
    products = WorkOrderProductSerializer(many=True, read_only=True)  # 一个施工单包含的多个产品
    materials = WorkOrderMaterialSerializer(many=True, read_only=True)
    
    progress_percentage = serializers.SerializerMethodField()
    # 多产品合并显示字段（用于基本信息显示）
    product_name = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkOrder
        fields = '__all__'
    
    def get_progress_percentage(self, obj):
        return obj.get_progress_percentage()
    
    def get_product_name(self, obj):
        """如果有多个产品，显示为 'xx款拼版'，否则显示单个产品名称"""
        products = obj.products.all()
        if products.count() > 1:
            return f'{products.count()}款拼版'
        elif products.count() == 1:
            return products.first().product_name
        else:
            # 如果没有关联产品，使用旧的单个产品字段
            return obj.product_name
    
    def get_quantity(self, obj):
        """如果有多个产品，返回所有产品的数量总和"""
        products = obj.products.all()
        if products.count() > 0:
            return sum(p.quantity for p in products)
        else:
            # 如果没有关联产品，使用旧的单个产品数量
            return obj.quantity or 0
    
    def get_unit(self, obj):
        """如果有多个产品，返回第一个产品的单位"""
        products = obj.products.all()
        if products.count() > 0:
            return products.first().unit
        else:
            # 如果没有关联产品，使用旧的单个产品单位
            return obj.unit or '件'


class WorkOrderCreateUpdateSerializer(serializers.ModelSerializer):
    """施工单创建/更新序列化器"""
    # 支持多个产品（一个施工单包含多个产品）
    products_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='产品列表数据，格式：[{"product": id, "quantity": 1, "unit": "件", "specification": "", "sort_order": 0}]'
    )
    
    class Meta:
        model = WorkOrder
        fields = [
            'id', 'order_number', 'customer', 'product', 'product_name',
            'specification', 'quantity', 'unit', 'status', 'priority',
            'order_date', 'delivery_date', 'actual_delivery_date',
            'total_amount', 'design_file', 'notes',
            'artwork', 'die', 'imposition_quantity',
            'products_data'
        ]
        read_only_fields = ['order_number']
    
    def validate(self, data):
        """验证数据，自动从产品中填充信息"""
        product = data.get('product')
        products_data = data.get('products_data', [])
        
        # 如果提供了 products_data，优先使用多产品模式
        if products_data:
            # 计算总金额
            total = 0
            for item in products_data:
                product_id = item.get('product')
                if product_id:
                    try:
                        product_obj = Product.objects.get(id=product_id)
                        quantity = item.get('quantity', 1)
                        total += product_obj.unit_price * quantity
                    except Product.DoesNotExist:
                        pass
            if total > 0:
                data['total_amount'] = total
        elif product and not self.instance:  # 创建时，单个产品模式
            # 自动填充产品相关信息
            data['product_name'] = product.name
            data['specification'] = product.specification
            data['unit'] = product.unit
            
            # 如果没有提供总价，根据产品单价和数量计算
            if 'total_amount' not in data or data['total_amount'] == 0:
                quantity = data.get('quantity', 1)
                data['total_amount'] = product.unit_price * quantity
        return data
    
    def create(self, validated_data):
        """创建施工单并处理多个产品"""
        products_data = validated_data.pop('products_data', [])
        work_order = WorkOrder.objects.create(**validated_data)
        
        # 创建关联的产品记录
        if products_data:
            for item in products_data:
                WorkOrderProduct.objects.create(
                    work_order=work_order,
                    product_id=item.get('product'),
                    quantity=item.get('quantity', 1),
                    unit=item.get('unit', '件'),
                    specification=item.get('specification', ''),
                    sort_order=item.get('sort_order', 0)
                )
        
        return work_order
    
    def update(self, instance, validated_data):
        """更新施工单并处理多个产品"""
        products_data = validated_data.pop('products_data', None)
        
        # 更新施工单基本信息
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # 如果提供了 products_data，更新产品列表
        if products_data is not None:
            # 删除现有产品关联
            WorkOrderProduct.objects.filter(work_order=instance).delete()
            
            # 创建新的产品关联
            for item in products_data:
                WorkOrderProduct.objects.create(
                    work_order=instance,
                    product_id=item.get('product'),
                    quantity=item.get('quantity', 1),
                    unit=item.get('unit', '件'),
                    specification=item.get('specification', ''),
                    sort_order=item.get('sort_order', 0)
                )
        
        return instance


class WorkOrderProcessUpdateSerializer(serializers.ModelSerializer):
    """工序更新序列化器"""
    
    class Meta:
        model = WorkOrderProcess
        fields = [
            'id', 'status', 'operator', 'actual_start_time',
            'actual_end_time', 'quantity_completed', 'quantity_defective', 'notes'
        ]


class ArtworkProductSerializer(serializers.ModelSerializer):
    """图稿产品序列化器"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    
    class Meta:
        model = ArtworkProduct
        fields = '__all__'


class ArtworkSerializer(serializers.ModelSerializer):
    """图稿序列化器"""
    products = ArtworkProductSerializer(many=True, read_only=True)
    products_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='产品列表数据，格式：[{"product": 1, "imposition_quantity": 2}]'
    )
    
    class Meta:
        model = Artwork
        fields = '__all__'
        # code 字段不在 read_only_fields 中，允许自定义输入
    
    def create(self, validated_data):
        """创建图稿，如果编码为空则自动生成，并创建关联产品"""
        products_data = validated_data.pop('products_data', [])
        
        # 如果编码为空，自动生成
        if not validated_data.get('code'):
            validated_data['code'] = Artwork.generate_code()
        
        artwork = super().create(validated_data)
        
        # 创建关联产品
        for idx, product_data in enumerate(products_data):
            ArtworkProduct.objects.create(
                artwork=artwork,
                product_id=product_data.get('product'),
                imposition_quantity=product_data.get('imposition_quantity', 1),
                sort_order=idx
            )
        
        return artwork
    
    def update(self, instance, validated_data):
        """更新图稿，处理产品列表"""
        products_data = validated_data.pop('products_data', None)
        
        artwork = super().update(instance, validated_data)
        
        # 如果提供了产品数据，更新产品列表
        if products_data is not None:
            # 删除现有产品关联
            ArtworkProduct.objects.filter(artwork=artwork).delete()
            
            # 创建新的产品关联
            for idx, product_data in enumerate(products_data):
                ArtworkProduct.objects.create(
                    artwork=artwork,
                    product_id=product_data.get('product'),
                    imposition_quantity=product_data.get('imposition_quantity', 1),
                    sort_order=idx
                )
        
        return artwork


class DieProductSerializer(serializers.ModelSerializer):
    """刀模产品序列化器"""
    product_name = serializers.SerializerMethodField()
    product_code = serializers.SerializerMethodField()
    
    class Meta:
        model = DieProduct
        fields = '__all__'
    
    def get_product_name(self, obj):
        return obj.product.name if obj.product else None
    
    def get_product_code(self, obj):
        return obj.product.code if obj.product else None


class DieSerializer(serializers.ModelSerializer):
    """刀模序列化器"""
    products = DieProductSerializer(many=True, read_only=True)
    products_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='产品列表数据，格式：[{"product": 1, "quantity": 2}]'
    )
    
    class Meta:
        model = Die
        fields = '__all__'
        # code 字段不在 read_only_fields 中，允许自定义输入
    
    def create(self, validated_data):
        """创建刀模，如果编码为空则自动生成，并创建关联产品"""
        products_data = validated_data.pop('products_data', [])
        
        # 如果编码为空，自动生成
        if not validated_data.get('code'):
            validated_data['code'] = Die.generate_code()
        
        die = super().create(validated_data)
        
        # 创建关联产品
        for idx, product_data in enumerate(products_data):
            DieProduct.objects.create(
                die=die,
                product_id=product_data.get('product'),
                quantity=product_data.get('quantity', 1),
                sort_order=idx
            )
        
        return die
    
    def update(self, instance, validated_data):
        """更新刀模，处理产品列表"""
        products_data = validated_data.pop('products_data', None)
        
        die = super().update(instance, validated_data)
        
        # 如果提供了产品数据，更新产品列表
        if products_data is not None:
            # 删除现有产品关联
            DieProduct.objects.filter(die=die).delete()
            
            # 创建新的产品关联
            for idx, product_data in enumerate(products_data):
                DieProduct.objects.create(
                    die=die,
                    product_id=product_data.get('product'),
                    quantity=product_data.get('quantity', 1),
                    sort_order=idx
                )
        
        return die

