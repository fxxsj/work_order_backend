from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Customer, Department, Process, Product, ProductMaterial, Material, WorkOrder,
    WorkOrderProcess, WorkOrderMaterial, WorkOrderProduct, ProcessLog, Artwork, ArtworkProduct,
    Die, DieProduct, WorkOrderTask, ProductGroup, ProductGroupItem
)


class UserSerializer(serializers.ModelSerializer):
    """用户序列化器"""
    groups = serializers.SerializerMethodField()
    is_salesperson = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'groups', 'is_salesperson']
    
    def get_groups(self, obj):
        """获取用户所属的组"""
        return list(obj.groups.values_list('name', flat=True))
    
    def get_is_salesperson(self, obj):
        """判断用户是否为业务员"""
        return obj.groups.filter(name='业务员').exists()


class CustomerSerializer(serializers.ModelSerializer):
    """客户序列化器"""
    salesperson_name = serializers.CharField(source='salesperson.username', read_only=True, allow_null=True)
    
    class Meta:
        model = Customer
        fields = '__all__'


class DepartmentSerializer(serializers.ModelSerializer):
    """部门序列化器"""
    processes = serializers.PrimaryKeyRelatedField(many=True, queryset=Process.objects.all(), required=False)
    process_names = serializers.SerializerMethodField()
    
    class Meta:
        model = Department
        fields = '__all__'
    
    def get_process_names(self, obj):
        """获取工序名称列表"""
        if hasattr(obj, 'processes'):
            return [f"{p.code} - {p.name}" for p in obj.processes.all()]
        return []


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
    task_type_display = serializers.CharField(source='get_task_type_display', read_only=True)
    artwork_code = serializers.SerializerMethodField()
    artwork_name = serializers.SerializerMethodField()
    artwork_confirmed = serializers.SerializerMethodField()
    die_code = serializers.SerializerMethodField()
    die_name = serializers.SerializerMethodField()
    product_code = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    material_code = serializers.SerializerMethodField()
    material_name = serializers.SerializerMethodField()
    # 物料状态（用于采购和开料任务）
    material_purchase_status = serializers.SerializerMethodField()
    # 工序和施工单信息
    work_order_process_info = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkOrderTask
        fields = '__all__'
        # 在更新时，某些字段应该是只读的
        read_only_fields = ['work_order_process', 'task_type', 'work_content', 'production_quantity', 
                          'artwork', 'die', 'product', 'material', 'auto_calculate_quantity', 
                          'production_requirements', 'created_at']
    
    def get_artwork_code(self, obj):
        """获取图稿编码"""
        if obj.artwork:
            return obj.artwork.get_full_code()
        return None
    
    def get_artwork_name(self, obj):
        """获取图稿名称"""
        if obj.artwork:
            return obj.artwork.name
        return None
    
    def get_artwork_confirmed(self, obj):
        """获取图稿确认状态"""
        if obj.artwork:
            return obj.artwork.confirmed
        return None
    
    def get_die_code(self, obj):
        """获取刀模编码"""
        if obj.die:
            return obj.die.code
        return None
    
    def get_die_name(self, obj):
        """获取刀模名称"""
        if obj.die:
            return obj.die.name
        return None
    
    def get_product_code(self, obj):
        """获取产品编码"""
        if obj.product:
            return obj.product.code
        return None
    
    def get_product_name(self, obj):
        """获取产品名称"""
        if obj.product:
            return obj.product.name
        return None
    
    def get_material_code(self, obj):
        """获取物料编码"""
        if obj.material:
            return obj.material.code
        return None
    
    def get_material_name(self, obj):
        """获取物料名称"""
        if obj.material:
            return obj.material.name
        return None
    
    def get_material_purchase_status(self, obj):
        """获取物料采购状态"""
        if obj.material and obj.work_order_process:
            try:
                material_record = WorkOrderMaterial.objects.get(
                    work_order=obj.work_order_process.work_order,
                    material=obj.material
                )
                return material_record.purchase_status
            except WorkOrderMaterial.DoesNotExist:
                return None
        return None
    
    def get_work_order_process_info(self, obj):
        """获取工序和施工单信息"""
        if obj.work_order_process:
            process = obj.work_order_process.process
            work_order = obj.work_order_process.work_order
            return {
                'process': {
                    'id': process.id if process else None,
                    'name': process.name if process else None,
                    'code': process.code if process else None
                },
                'work_order': {
                    'id': work_order.id if work_order else None,
                    'order_number': work_order.order_number if work_order else None
                }
            }
        return None


class WorkOrderProcessSerializer(serializers.ModelSerializer):
    """施工单工序序列化器"""
    process_name = serializers.CharField(source='process.name', read_only=True)
    process_code = serializers.CharField(source='process.code', read_only=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)
    department_code = serializers.CharField(source='department.code', read_only=True, allow_null=True)
    can_start = serializers.SerializerMethodField()
    logs = ProcessLogSerializer(many=True, read_only=True)
    tasks = WorkOrderTaskSerializer(many=True, read_only=True)
    
    class Meta:
        model = WorkOrderProcess
        fields = '__all__'
    
    def get_can_start(self, obj):
        """判断工序是否可以开始"""
        return obj.can_start()


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
    imposition_quantity = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkOrderProduct
        fields = '__all__'
    
    def get_imposition_quantity(self, obj):
        """从图稿产品关联中获取拼版数量"""
        # 获取施工单的图稿
        work_order = obj.work_order
        if not work_order:
            return 1
        
        # 获取施工单关联的图稿
        artworks = work_order.artworks.all()
        if not artworks:
            return 1
        
        # 遍历图稿，查找该产品的拼版数量
        for artwork in artworks:
            try:
                artwork_product = ArtworkProduct.objects.filter(
                    artwork=artwork,
                    product=obj.product
                ).first()
                if artwork_product:
                    return artwork_product.imposition_quantity
            except:
                continue
        
        # 如果找不到，返回默认值1
        return 1


class WorkOrderMaterialSerializer(serializers.ModelSerializer):
    """施工单物料序列化器"""
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_unit = serializers.CharField(source='material.unit', read_only=True)
    purchase_status_display = serializers.CharField(source='get_purchase_status_display', read_only=True)
    
    class Meta:
        model = WorkOrderMaterial
        fields = [
            'id', 'work_order', 'material', 'material_name', 'material_code', 'material_unit',
            'material_size', 'material_usage', 'notes',
            'purchase_status', 'purchase_status_display',
            'purchase_date', 'received_date', 'cut_date',
            'created_at'
        ]


class WorkOrderListSerializer(serializers.ModelSerializer):
    """施工单列表序列化器（精简版）"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    salesperson_name = serializers.CharField(source='customer.salesperson.username', read_only=True, allow_null=True)
    product_code = serializers.CharField(source='product.code', read_only=True, allow_null=True)
    manager_name = serializers.CharField(source='manager.username', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, allow_null=True)
    approval_status_display = serializers.CharField(source='get_approval_status_display', read_only=True)
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
            'id', 'order_number', 'customer', 'customer_name', 'salesperson_name',
            'product', 'product_code', 'product_name', 'quantity', 'unit', 'status', 'status_display',
            'priority', 'priority_display', 'order_date', 'delivery_date',
            'production_quantity', 'defective_quantity',
            'total_amount', 'manager', 'manager_name', 'progress_percentage',
            'approval_status', 'approval_status_display', 'approved_by_name', 'approved_at', 'approval_comment',
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
            # WorkOrderProduct 通过 product 关联获取产品名称
            first_product = products.first()
            return first_product.product.name if first_product.product else None
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
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, allow_null=True)
    approval_status_display = serializers.CharField(source='get_approval_status_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    printing_type_display = serializers.CharField(source='get_printing_type_display', read_only=True)
    printing_cmyk_colors = serializers.JSONField(read_only=True)
    printing_other_colors = serializers.JSONField(read_only=True)
    printing_colors_display = serializers.SerializerMethodField()
    # 图稿类型
    artwork_type = serializers.CharField(read_only=True)
    artwork_type_display = serializers.CharField(source='get_artwork_type_display', read_only=True)
    # 图稿信息：支持多个图稿（使用 PrimaryKeyRelatedField，避免循环引用）
    artworks = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    artwork_names = serializers.SerializerMethodField()
    artwork_codes = serializers.SerializerMethodField()
    # 图稿详细信息（包含确认状态）
    artwork_details = serializers.SerializerMethodField()
    artwork_colors = serializers.SerializerMethodField()  # 图稿色数信息
    # 刀模类型
    die_type = serializers.CharField(read_only=True)
    die_type_display = serializers.CharField(source='get_die_type_display', read_only=True)
    # 刀模信息：支持多个刀模
    dies = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    die_names = serializers.SerializerMethodField()
    die_codes = serializers.SerializerMethodField()
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
            # WorkOrderProduct 通过 product 关联获取产品名称
            first_product = products.first()
            return first_product.product.name if first_product.product else None
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
    
    def get_artwork_names(self, obj):
        """获取所有图稿名称"""
        return [artwork.name for artwork in obj.artworks.all()]
    
    def get_artwork_codes(self, obj):
        """获取所有图稿编码（完整编码，包含版本号）"""
        return [artwork.get_full_code() for artwork in obj.artworks.all()]
    
    def get_artwork_details(self, obj):
        """获取图稿详细信息（包含确认状态）"""
        artworks = obj.artworks.all()
        return [
            {
                'id': artwork.id,
                'code': artwork.get_full_code(),
                'name': artwork.name,
                'confirmed': artwork.confirmed,
                'confirmed_by_name': artwork.confirmed_by.username if artwork.confirmed_by else None,
                'confirmed_at': artwork.confirmed_at
            }
            for artwork in artworks
        ]
    
    def get_artwork_colors(self, obj):
        """获取所有图稿的色数信息"""
        artworks = obj.artworks.all()
        if not artworks:
            return None
        
        # 获取所有图稿的色数显示，用逗号分隔
        color_displays = []
        for artwork in artworks:
            # 使用与ArtworkSerializer相同的逻辑生成色数显示
            parts = []
            total_count = 0
            
            # CMYK颜色：按照固定顺序C、M、Y、K排列
            if artwork.cmyk_colors:
                cmyk_order = ['C', 'M', 'Y', 'K']
                cmyk_sorted = [c for c in cmyk_order if c in artwork.cmyk_colors]
                if cmyk_sorted:
                    cmyk_str = ''.join(cmyk_sorted)
                    parts.append(cmyk_str)
                    total_count += len(artwork.cmyk_colors)
            
            # 其他颜色：用逗号分隔
            if artwork.other_colors:
                other_colors_list = [c.strip() for c in artwork.other_colors if c and c.strip()]
                if other_colors_list:
                    other_colors_str = ','.join(other_colors_list)
                    parts.append(other_colors_str)
                    total_count += len(other_colors_list)
            
            # 组合显示
            if len(parts) > 1:
                result = '+'.join(parts)
            elif len(parts) == 1:
                result = parts[0]
            else:
                continue
            
            # 添加色数统计
            if total_count > 0:
                result += f'（{total_count}色）'
            
            color_displays.append(result)
        
        return ', '.join(color_displays) if color_displays else None
    
    def get_printing_colors_display(self, obj):
        """生成印刷色数显示格式"""
        parts = []
        total_count = 0
        
        # CMYK颜色：按照固定顺序C、M、Y、K排列
        if obj.printing_cmyk_colors:
            cmyk_order = ['C', 'M', 'Y', 'K']
            cmyk_sorted = [c for c in cmyk_order if c in obj.printing_cmyk_colors]
            if cmyk_sorted:
                cmyk_str = ''.join(cmyk_sorted)
                parts.append(cmyk_str)
                total_count += len(obj.printing_cmyk_colors)
        
        # 其他颜色：用逗号分隔
        if obj.printing_other_colors:
            other_colors_list = [c.strip() for c in obj.printing_other_colors if c and c.strip()]
            if other_colors_list:
                other_colors_str = ','.join(other_colors_list)
                parts.append(other_colors_str)
                total_count += len(other_colors_list)
        
        # 组合显示
        if len(parts) > 1:
            result = '+'.join(parts)
        elif len(parts) == 1:
            result = parts[0]
        else:
            return None
        
        # 添加色数统计
        if total_count > 0:
            result += f'（{total_count}色）'
        
        return result
    
    def get_die_names(self, obj):
        """获取所有刀模名称"""
        return [die.name for die in obj.dies.all()]
    
    def get_die_codes(self, obj):
        """获取所有刀模编码"""
        return [die.code for die in obj.dies.all()]


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
            'production_quantity', 'defective_quantity',
            'total_amount', 'design_file', 'notes',
            'artwork_type', 'artworks', 'die_type', 'dies', 'printing_type', 'printing_cmyk_colors', 'printing_other_colors',
            'products_data'
        ]
        read_only_fields = ['order_number']
    
    def validate(self, data):
        """验证数据，自动从产品中填充信息"""
        product = data.get('product')
        products_data = data.get('products_data', [])
        artworks = data.get('artworks', [])
        dies = data.get('dies', [])
        printing_type = data.get('printing_type')
        artwork_type = data.get('artwork_type', 'no_artwork')
        die_type = data.get('die_type', 'no_die')
        
        # 根据图稿类型验证图稿选择
        if artwork_type in ['need_update', 'old_artwork']:
            # 需更新图稿和旧图稿必须选择至少一个图稿
            if not artworks or len(artworks) == 0:
                raise serializers.ValidationError({
                    'artworks': '选择"需更新图稿"或"旧图稿"时，请至少选择一个图稿'
                })
        
        # 根据刀模类型验证刀模选择
        if die_type in ['need_update', 'old_die']:
            # 需更新刀模和旧刀模必须选择至少一个刀模
            if not dies or len(dies) == 0:
                raise serializers.ValidationError({
                    'dies': '选择"需更新刀模"或"旧刀模"时，请至少选择一个刀模'
                })
        
        # 如果没有选择图稿，自动设置印刷形式为"不需要印刷"
        if not artworks or len(artworks) == 0:
            data['printing_type'] = 'none'
        elif printing_type == 'none':
            # 如果选择了图稿但印刷形式是"不需要印刷"，默认改为"正面印刷"
            data['printing_type'] = 'front'
        
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
        """创建施工单并处理多个产品和图稿"""
        products_data = validated_data.pop('products_data', [])
        artworks = validated_data.pop('artworks', [])
        dies = validated_data.pop('dies', [])
        
        work_order = WorkOrder.objects.create(**validated_data)
        
        # 设置图稿（ManyToMany 字段需要在对象创建后设置）
        if artworks:
            work_order.artworks.set(artworks)
        
        # 设置刀模（ManyToMany 字段需要在对象创建后设置）
        if dies:
            work_order.dies.set(dies)
        
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
        
        # 自动创建工序
        self._create_work_order_processes(work_order)
        
        return work_order
    
    def update(self, instance, validated_data):
        """更新施工单并处理多个产品和图稿"""
        products_data = validated_data.pop('products_data', None)
        artworks = validated_data.pop('artworks', None)
        dies = validated_data.pop('dies', None)
        
        # 更新图稿（ManyToMany 字段）
        if artworks is not None:
            instance.artworks.set(artworks)
            # 如果没有选择图稿，自动设置印刷形式为"不需要印刷"
            if not artworks or len(artworks) == 0:
                validated_data['printing_type'] = 'none'
            elif validated_data.get('printing_type') == 'none':
                # 如果选择了图稿但印刷形式是"不需要印刷"，默认改为"正面印刷"
                validated_data['printing_type'] = 'front'
        
        # 更新施工单基本信息
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # 更新刀模（ManyToMany 字段）
        if dies is not None:
            instance.dies.set(dies)
        
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
            
            # 如果产品列表发生变化，重新创建工序
            self._recreate_work_order_processes(instance)
        
        return instance
    
    def _create_work_order_processes(self, work_order):
        """为施工单自动创建工序"""
        # 收集所有产品的默认工序
        processes = set()
        
        # 从 products 关联中获取
        for product_item in work_order.products.all():
            processes.update(product_item.product.default_processes.all())
        
        # 兼容旧数据：如果使用单个 product 字段
        if work_order.product:
            processes.update(work_order.product.default_processes.all())
        
        # 为每个工序创建 WorkOrderProcess
        for process in sorted(processes, key=lambda p: p.sort_order):
            # 查找负责该工序的部门（可能有多个，选择第一个）
            departments = Department.objects.filter(processes=process, is_active=True)
            department = departments.first() if departments.exists() else None
            
            WorkOrderProcess.objects.get_or_create(
                work_order=work_order,
                process=process,
                defaults={
                    'department': department,
                    'sequence': process.sort_order
                }
            )
    
    def _recreate_work_order_processes(self, work_order):
        """重新创建施工单的工序（当产品列表变化时）"""
        # 删除现有的工序（如果还没有开始）
        WorkOrderProcess.objects.filter(
            work_order=work_order,
            status='pending'
        ).delete()
        
        # 重新创建工序
        self._create_work_order_processes(work_order)


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
    # 色数显示（计算字段）
    color_display = serializers.SerializerMethodField()
    # 刀模信息
    die_names = serializers.SerializerMethodField()
    die_codes = serializers.SerializerMethodField()
    # 完整编码（包含版本号），用于向后兼容
    code = serializers.SerializerMethodField()
    # 确认信息
    confirmed_by_name = serializers.CharField(source='confirmed_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = Artwork
        fields = '__all__'
        # base_code 字段不在 read_only_fields 中，允许自定义输入
    
    def get_color_display(self, obj):
        """生成色数显示文本，格式：CMK+928C,金色（5色）"""
        parts = []
        total_count = 0
        
        # CMYK颜色：按照固定顺序C、M、Y、K排列
        if obj.cmyk_colors:
            cmyk_order = ['C', 'M', 'Y', 'K']  # 固定顺序：1C2M3Y4K
            cmyk_sorted = [c for c in cmyk_order if c in obj.cmyk_colors]
            if cmyk_sorted:
                cmyk_str = ''.join(cmyk_sorted)  # 按固定顺序连接，如：CMK
                parts.append(cmyk_str)
                total_count += len(obj.cmyk_colors)
        
        # 其他颜色：用逗号分隔
        if obj.other_colors:
            other_colors_list = [c.strip() for c in obj.other_colors if c and c.strip()]
            if other_colors_list:
                other_colors_str = ','.join(other_colors_list)  # 用逗号分隔
                parts.append(other_colors_str)
                total_count += len(other_colors_list)
        
        # 组合显示：如果有CMYK和其他颜色，用+号连接
        if len(parts) > 1:
            result = '+'.join(parts)
        elif len(parts) == 1:
            result = parts[0]
        else:
            return '-'
        
        # 添加色数统计
        if total_count > 0:
            result += f'（{total_count}色）'
        
        return result
    
    def get_die_names(self, obj):
        """获取所有刀模名称"""
        return [die.name for die in obj.dies.all()]
    
    def get_die_codes(self, obj):
        """获取所有刀模编码"""
        return [die.code for die in obj.dies.all()]
    
    def get_code(self, obj):
        """获取完整编码（包含版本号），用于向后兼容"""
        return obj.get_full_code()
    
    def create(self, validated_data):
        """创建图稿，如果主编码为空则自动生成，并创建关联产品"""
        products_data = validated_data.pop('products_data', [])
        
        # 如果主编码为空，自动生成
        if not validated_data.get('base_code'):
            validated_data['base_code'] = Artwork.generate_base_code()
        
        # 如果指定了 base_code 但没有指定 version，自动获取下一个版本号
        if validated_data.get('base_code') and 'version' not in validated_data:
            validated_data['version'] = Artwork.get_next_version(validated_data['base_code'])
        
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

