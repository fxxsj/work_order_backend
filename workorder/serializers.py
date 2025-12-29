from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Customer, ProcessCategory, Process, Product, ProductMaterial, Material, WorkOrder,
    WorkOrderProcess, WorkOrderMaterial, ProcessLog, Artwork, ArtworkProduct,
    Die, DieProduct
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


class ProcessCategorySerializer(serializers.ModelSerializer):
    """工序分类序列化器"""
    class Meta:
        model = ProcessCategory
        fields = '__all__'


class ProcessSerializer(serializers.ModelSerializer):
    """工序序列化器"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)
    
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


class WorkOrderProcessSerializer(serializers.ModelSerializer):
    """施工单工序序列化器"""
    process_name = serializers.CharField(source='process.name', read_only=True)
    process_code = serializers.CharField(source='process.code', read_only=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    logs = ProcessLogSerializer(many=True, read_only=True)
    
    class Meta:
        model = WorkOrderProcess
        fields = '__all__'


class WorkOrderMaterialSerializer(serializers.ModelSerializer):
    """施工单物料序列化器"""
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_unit = serializers.CharField(source='material.unit', read_only=True)
    
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


class WorkOrderDetailSerializer(serializers.ModelSerializer):
    """施工单详情序列化器（完整版）"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_detail = CustomerSerializer(source='customer', read_only=True)
    product_detail = ProductSerializer(source='product', read_only=True)
    manager_name = serializers.CharField(source='manager.username', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    
    order_processes = WorkOrderProcessSerializer(many=True, read_only=True)
    materials = WorkOrderMaterialSerializer(many=True, read_only=True)
    
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkOrder
        fields = '__all__'
    
    def get_progress_percentage(self, obj):
        return obj.get_progress_percentage()


class WorkOrderCreateUpdateSerializer(serializers.ModelSerializer):
    """施工单创建/更新序列化器"""
    
    class Meta:
        model = WorkOrder
        fields = [
            'id', 'order_number', 'customer', 'product', 'product_name',
            'specification', 'quantity', 'unit', 'status', 'priority',
            'order_date', 'delivery_date', 'actual_delivery_date',
            'total_amount', 'design_file', 'notes',
            'paper_type', 'paper_weight', 'paper_brand', 'board_thickness',
            'material_size', 'material_usage', 'material_notes'
        ]
        read_only_fields = ['order_number']
    
    def validate(self, data):
        """验证数据，自动从产品中填充信息"""
        product = data.get('product')
        if product and not self.instance:  # 创建时
            # 自动填充产品相关信息
            data['product_name'] = product.name
            data['specification'] = product.specification
            data['unit'] = product.unit
            
            # 自动填充主材信息（如果产品有默认值且用户未提供）
            if not data.get('paper_type') and product.paper_type:
                data['paper_type'] = product.paper_type
            if not data.get('paper_weight') and product.paper_weight:
                data['paper_weight'] = product.paper_weight
            if not data.get('paper_brand') and product.paper_brand:
                data['paper_brand'] = product.paper_brand
            if not data.get('board_thickness') and product.board_thickness:
                data['board_thickness'] = product.board_thickness
            if not data.get('material_size') and product.material_size:
                data['material_size'] = product.material_size
            if not data.get('material_usage') and product.material_usage:
                data['material_usage'] = product.material_usage
            
            # 如果没有提供总价，根据产品单价和数量计算
            if 'total_amount' not in data or data['total_amount'] == 0:
                quantity = data.get('quantity', 1)
                data['total_amount'] = product.unit_price * quantity
        return data


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
        read_only_fields = ['code']
    
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

