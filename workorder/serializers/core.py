"""
核心业务序列化器模块

包含施工单、工序、任务、日志等核心业务的序列化器。
"""

from rest_framework import serializers
from ..models.core import (
    WorkOrder, WorkOrderProcess, WorkOrderProduct, WorkOrderMaterial,
    WorkOrderTask, ProcessLog, TaskLog, APPROVED_ORDER_PROTECTED_FIELDS
)
from ..models.base import Process, Department
from ..models.products import Product
from ..models.assets import ArtworkProduct


class ProcessLogSerializer(serializers.ModelSerializer):
    """工序日志序列化器"""
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)

    class Meta:
        model = ProcessLog
        fields = '__all__'


class TaskLogSerializer(serializers.ModelSerializer):
    """任务操作日志序列化器"""
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)
    operator_name = serializers.SerializerMethodField()
    quantity_increment = serializers.SerializerMethodField()  # 增量值（优先使用模型字段，如果没有则计算）

    class Meta:
        model = TaskLog
        fields = '__all__'

    def get_operator_name(self, obj):
        """获取操作员名称"""
        if obj.operator:
            return obj.operator.username
        return None

    def get_quantity_increment(self, obj):
        """获取增量值（优先使用模型字段，如果没有则计算）"""
        if obj.quantity_increment is not None:
            return obj.quantity_increment
        # 兼容旧数据：如果没有增量字段，则计算
        if obj.quantity_before is not None and obj.quantity_after is not None:
            return obj.quantity_after - obj.quantity_before
        return None


class WorkOrderTaskSerializer(serializers.ModelSerializer):
    """施工单任务序列化器"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_draft = serializers.SerializerMethodField()
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
    foiling_plate_code = serializers.SerializerMethodField()
    foiling_plate_name = serializers.SerializerMethodField()
    embossing_plate_code = serializers.SerializerMethodField()
    embossing_plate_name = serializers.SerializerMethodField()
    # 物料状态（用于采购和开料任务）
    material_purchase_status = serializers.SerializerMethodField()
    # 工序和施工单信息
    work_order_process_info = serializers.SerializerMethodField()
    # 任务操作历史
    logs = TaskLogSerializer(many=True, read_only=True)
    # 分派信息
    assigned_department_name = serializers.CharField(source='assigned_department.name', read_only=True, allow_null=True)
    assigned_operator_name = serializers.SerializerMethodField()
    # 任务拆分信息
    is_subtask = serializers.SerializerMethodField()
    subtasks_count = serializers.SerializerMethodField()
    parent_task_id = serializers.IntegerField(source='parent_task.id', read_only=True, allow_null=True)

    class Meta:
        model = WorkOrderTask
        fields = '__all__'
        # 在更新时，某些字段应该是只读的
        read_only_fields = ['work_order_process', 'task_type', 'work_content', 'production_quantity',
                          'artwork', 'die', 'product', 'material', 'foiling_plate', 'embossing_plate',
                          'auto_calculate_quantity', 'created_at']

    def get_assigned_operator_name(self, obj):
        """获取分派操作员名称"""
        if obj.assigned_operator:
            return f"{obj.assigned_operator.first_name}{obj.assigned_operator.last_name}"
        return None

    def get_is_draft(self, obj):
        """判断是否为草稿状态"""
        return obj.status == 'draft'

    def get_is_subtask(self, obj):
        """判断是否为子任务"""
        return obj.is_subtask()

    def get_subtasks_count(self, obj):
        """获取子任务数量"""
        if obj.pk:
            return obj.subtasks.count()
        return 0

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

    def get_foiling_plate_code(self, obj):
        """获取烫金版编码"""
        if obj.foiling_plate:
            return obj.foiling_plate.code
        return None

    def get_foiling_plate_name(self, obj):
        """获取烫金版名称"""
        if obj.foiling_plate:
            return obj.foiling_plate.name
        return None

    def get_embossing_plate_code(self, obj):
        """获取压凸版编码"""
        if obj.embossing_plate:
            return obj.embossing_plate.code
        return None

    def get_embossing_plate_name(self, obj):
        """获取压凸版名称"""
        if obj.embossing_plate:
            return obj.embossing_plate.name
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
            # 获取与工序关联的部门
            departments = []
            if process:
                # 使用反向关系 department_set 来访问关联的部门
                departments = [
                    {
                        'id': dept.id,
                        'name': dept.name,
                        'code': dept.code
                    }
                    for dept in process.department_set.filter(is_active=True).order_by('sort_order')
                ]
            return {
                'process': {
                    'id': process.id if process else None,
                    'name': process.name if process else None,
                    'code': process.code if process else None,
                    'departments': departments  # 添加关联的部门列表
                },
                'work_order': {
                    'id': work_order.id if work_order else None,
                    'order_number': work_order.order_number if work_order else None,
                    'priority': work_order.priority if work_order else None,
                    'priority_display': work_order.get_priority_display() if work_order else None,
                    'delivery_date': work_order.delivery_date.strftime('%Y-%m-%d') if work_order and work_order.delivery_date else None
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


class WorkOrderProductSerializer(serializers.ModelSerializer):
    """施工单产品序列化器"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_detail = serializers.SerializerMethodField()
    imposition_quantity = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrderProduct
        fields = '__all__'

    def get_product_detail(self, obj):
        """获取产品详细信息"""
        from .products import ProductSerializer
        return ProductSerializer(obj.product).data if obj.product else None

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
            'material_size', 'material_usage', 'need_cutting', 'notes',
            'purchase_status', 'purchase_status_display',
            'purchase_date', 'received_date', 'cut_date',
            'created_at'
        ]


class WorkOrderListSerializer(serializers.ModelSerializer):
    """施工单列表序列化器（精简版）"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    salesperson_name = serializers.CharField(source='customer.salesperson.username', read_only=True, allow_null=True)
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
    # 草稿任务统计
    draft_task_count = serializers.SerializerMethodField()
    total_task_count = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrder
        fields = [
            'id', 'order_number', 'customer', 'customer_name', 'salesperson_name',
            'product_name', 'quantity', 'unit', 'status', 'status_display',
            'priority', 'priority_display', 'order_date', 'delivery_date',
            'production_quantity', 'defective_quantity',
            'total_amount', 'manager', 'manager_name', 'progress_percentage',
            'approval_status', 'approval_status_display', 'approved_by_name', 'approved_at', 'approval_comment',
            'draft_task_count', 'total_task_count',
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
            first_product = products.first()
            return first_product.product.name if first_product.product else None
        return None

    def get_quantity(self, obj):
        """返回所有产品的数量总和"""
        products = obj.products.all()
        if products.exists():
            return sum(p.quantity for p in products)
        return 0

    def get_unit(self, obj):
        """返回第一个产品的单位"""
        products = obj.products.all()
        if products.exists():
            return products.first().unit
        return '件'

    def get_draft_task_count(self, obj):
        """获取草稿任务数量"""
        from ..models import WorkOrderTask
        return WorkOrderTask.objects.filter(
            work_order_process__work_order=obj,
            status='draft'
        ).count()

    def get_total_task_count(self, obj):
        """获取总任务数量"""
        from ..models import WorkOrderTask
        return WorkOrderTask.objects.filter(
            work_order_process__work_order=obj
        ).count()


class WorkOrderDetailSerializer(serializers.ModelSerializer):
    """施工单详情序列化器（完整版）"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_detail = serializers.SerializerMethodField()
    manager_name = serializers.CharField(source='manager.username', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, allow_null=True)
    approval_status_display = serializers.CharField(source='get_approval_status_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    printing_type_display = serializers.CharField(source='get_printing_type_display', read_only=True)
    printing_cmyk_colors = serializers.JSONField(read_only=True)
    printing_other_colors = serializers.JSONField(read_only=True)
    printing_colors_display = serializers.SerializerMethodField()
    # 图稿信息：支持多个图稿（使用 PrimaryKeyRelatedField，避免循环引用）
    artworks = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    artwork_names = serializers.SerializerMethodField()
    artwork_codes = serializers.SerializerMethodField()
    # 图稿详细信息（包含确认状态）
    artwork_details = serializers.SerializerMethodField()
    artwork_colors = serializers.SerializerMethodField()  # 图稿色数信息
    # 刀模信息：支持多个刀模
    dies = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    die_names = serializers.SerializerMethodField()
    die_codes = serializers.SerializerMethodField()
    # 烫金版信息：支持多个烫金版
    foiling_plates = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    foiling_plate_names = serializers.SerializerMethodField()
    foiling_plate_codes = serializers.SerializerMethodField()
    # 压凸版信息：支持多个压凸版
    embossing_plates = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    embossing_plate_names = serializers.SerializerMethodField()
    embossing_plate_codes = serializers.SerializerMethodField()
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    order_processes = WorkOrderProcessSerializer(many=True, read_only=True)
    products = WorkOrderProductSerializer(many=True, read_only=True)  # 一个施工单包含的多个产品
    materials = WorkOrderMaterialSerializer(many=True, read_only=True)
    # 审核历史记录
    approval_logs = serializers.SerializerMethodField()

    progress_percentage = serializers.SerializerMethodField()
    # 多产品合并显示字段（用于基本信息显示）
    product_name = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    # 草稿任务统计
    draft_task_count = serializers.SerializerMethodField()
    total_task_count = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrder
        fields = '__all__'

    def get_progress_percentage(self, obj):
        return obj.get_progress_percentage()

    def get_customer_detail(self, obj):
        """获取客户详细信息"""
        from .base import CustomerSerializer
        return CustomerSerializer(obj.customer).data if obj.customer else None

    def get_product_name(self, obj):
        """如果有多个产品，显示为 'xx款拼版'，否则显示单个产品名称"""
        products = obj.products.all()
        if products.count() > 1:
            return f'{products.count()}款拼版'
        elif products.count() == 1:
            first_product = products.first()
            return first_product.product.name if first_product.product else None
        return None

    def get_quantity(self, obj):
        """返回所有产品的数量总和"""
        products = obj.products.all()
        if products.exists():
            return sum(p.quantity for p in products)
        return 0

    def get_unit(self, obj):
        """返回第一个产品的单位"""
        products = obj.products.all()
        if products.exists():
            return products.first().unit
        return '件'

    def get_draft_task_count(self, obj):
        """获取草稿任务数量"""
        from ..models import WorkOrderTask
        return WorkOrderTask.objects.filter(
            work_order_process__work_order=obj,
            status='draft'
        ).count()

    def get_total_task_count(self, obj):
        """获取总任务数量"""
        from ..models import WorkOrderTask
        return WorkOrderTask.objects.filter(
            work_order_process__work_order=obj
        ).count()

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

    def get_foiling_plate_names(self, obj):
        """获取所有烫金版名称"""
        return [plate.name for plate in obj.foiling_plates.all()]

    def get_foiling_plate_codes(self, obj):
        """获取所有烫金版编码"""
        return [plate.code for plate in obj.foiling_plates.all()]

    def get_embossing_plate_names(self, obj):
        """获取所有压凸版名称"""
        return [plate.name for plate in obj.embossing_plates.all()]

    def get_embossing_plate_codes(self, obj):
        """获取所有压凸版编码"""
        return [plate.code for plate in obj.embossing_plates.all()]

    def get_approval_logs(self, obj):
        """获取审核历史记录"""
        from .system import WorkOrderApprovalLogSerializer
        logs = obj.approval_logs.all()
        return WorkOrderApprovalLogSerializer(logs, many=True).data


class WorkOrderCreateUpdateSerializer(serializers.ModelSerializer):
    """施工单创建/更新序列化器"""
    # 支持多个产品（一个施工单包含多个产品）
    products_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='产品列表数据，格式：[{"product": id, "quantity": 1, "unit": "件", "specification": "", "sort_order": 0}]'
    )
    # 支持物料列表（与施工单一起创建）
    materials_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='物料列表数据，格式：[{"material": id, "material_size": "", "material_usage": "", "need_cutting": false, "notes": ""}]'
    )
    # 工序ID列表（用于验证版的选择）
    # 使用自定义方法来过滤 null 值
    processes = serializers.ListField(
        child=serializers.IntegerField(allow_null=True),  # 允许 null，然后在 validate 中过滤
        write_only=True,
        required=False,
        allow_empty=True,
        help_text='选中的工序ID列表，用于验证版的选择'
    )

    def validate_processes(self, value):
        """验证并过滤 processes 字段"""
        if value is None:
            return []
        # 过滤掉 None 值
        return [pid for pid in value if pid is not None]

    class Meta:
        model = WorkOrder
        fields = [
            'id', 'order_number', 'customer',
            'status', 'priority',
            'order_date', 'delivery_date', 'actual_delivery_date',
            'production_quantity', 'defective_quantity',
            'total_amount', 'design_file', 'notes',
            'artworks', 'dies', 'foiling_plates', 'embossing_plates',
            'printing_type', 'printing_cmyk_colors', 'printing_other_colors',
            'products_data', 'materials_data', 'processes'
        ]
        read_only_fields = ['order_number']

    def validate(self, data):
        """验证数据，根据工序验证版的选择"""
        products_data = data.get('products_data', [])
        artworks = data.get('artworks')  # 不设置默认值，以便区分是否发送
        dies = data.get('dies')  # 不设置默认值，以便区分是否发送
        foiling_plates = data.get('foiling_plates')  # 不设置默认值，以便区分是否发送
        embossing_plates = data.get('embossing_plates')  # 不设置默认值，以便区分是否发送
        printing_type = data.get('printing_type')
        process_ids = data.get('processes', [])

        # process_ids 已经在 validate_processes 方法中过滤了 null 值
        # 根据选中的工序验证版的选择（只验证发送的字段）
        if process_ids:
            processes = Process.objects.filter(id__in=process_ids, is_active=True)

            # 如果是更新操作，需要检查数据库中已有的版选择
            instance = getattr(self, 'instance', None)

            # 检查是否有工序需要图稿
            processes_requiring_artwork = processes.filter(requires_artwork=True)
            if processes_requiring_artwork.exists():
                processes_requiring_artwork_mandatory = processes_requiring_artwork.filter(artwork_required=True)
                if processes_requiring_artwork_mandatory.exists():
                    # 如果artworks字段被发送，使用发送的值；否则使用数据库中的值
                    artworks_to_check = artworks if artworks is not None else (list(instance.artworks.values_list('id', flat=True)) if instance else [])
                    if not artworks_to_check or len(artworks_to_check) == 0:
                        process_names = ', '.join([p.name for p in processes_requiring_artwork_mandatory])
                        raise serializers.ValidationError({
                            'artworks': f'选择了需要图稿的工序（{process_names}），请至少选择一个图稿'
                        })

            # 检查是否有工序需要刀模
            processes_requiring_die = processes.filter(requires_die=True)
            if processes_requiring_die.exists():
                processes_requiring_die_mandatory = processes_requiring_die.filter(die_required=True)
                if processes_requiring_die_mandatory.exists():
                    # 如果dies字段被发送，使用发送的值；否则使用数据库中的值
                    dies_to_check = dies if dies is not None else (list(instance.dies.values_list('id', flat=True)) if instance else [])
                    if not dies_to_check or len(dies_to_check) == 0:
                        process_names = ', '.join([p.name for p in processes_requiring_die_mandatory])
                        raise serializers.ValidationError({
                            'dies': f'选择了需要刀模的工序（{process_names}），请至少选择一个刀模'
                        })

            # 检查是否有工序需要烫金版
            processes_requiring_foiling_plate = processes.filter(requires_foiling_plate=True)
            if processes_requiring_foiling_plate.exists():
                processes_requiring_foiling_plate_mandatory = processes_requiring_foiling_plate.filter(foiling_plate_required=True)
                if processes_requiring_foiling_plate_mandatory.exists():
                    # 如果foiling_plates字段被发送，使用发送的值；否则使用数据库中的值
                    foiling_plates_to_check = foiling_plates if foiling_plates is not None else (list(instance.foiling_plates.values_list('id', flat=True)) if instance else [])
                    if not foiling_plates_to_check or len(foiling_plates_to_check) == 0:
                        process_names = ', '.join([p.name for p in processes_requiring_foiling_plate_mandatory])
                        raise serializers.ValidationError({
                            'foiling_plates': f'选择了需要烫金版的工序（{process_names}），请至少选择一个烫金版'
                        })

            # 检查是否有工序需要压凸版
            processes_requiring_embossing_plate = processes.filter(requires_embossing_plate=True)
            if processes_requiring_embossing_plate.exists():
                processes_requiring_embossing_plate_mandatory = processes_requiring_embossing_plate.filter(embossing_plate_required=True)
                if processes_requiring_embossing_plate_mandatory.exists():
                    # 如果embossing_plates字段被发送，使用发送的值；否则使用数据库中的值
                    embossing_plates_to_check = embossing_plates if embossing_plates is not None else (list(instance.embossing_plates.values_list('id', flat=True)) if instance else [])
                    if not embossing_plates_to_check or len(embossing_plates_to_check) == 0:
                        process_names = ', '.join([p.name for p in processes_requiring_embossing_plate_mandatory])
                        raise serializers.ValidationError({
                            'embossing_plates': f'选择了需要压凸版的工序（{process_names}），请至少选择一个压凸版'
                        })

        # 只有在 artworks 字段被发送时才处理 printing_type
        if 'artworks' in data:
            artworks_value = artworks if artworks is not None else []
            if not artworks_value or len(artworks_value) == 0:
                data['printing_type'] = 'none'
            elif printing_type == 'none':
                # 如果选择了图稿但印刷形式是"不需要印刷"，默认改为"正面印刷"
                data['printing_type'] = 'front'

        # 如果提供了 products_data，计算总金额
        if products_data:
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

        return data

    def create(self, validated_data):
        """创建施工单并处理多个产品和图稿"""
        products_data = validated_data.pop('products_data', [])
        materials_data = validated_data.pop('materials_data', [])
        artworks = validated_data.pop('artworks', [])
        dies = validated_data.pop('dies', [])
        foiling_plates = validated_data.pop('foiling_plates', [])
        embossing_plates = validated_data.pop('embossing_plates', [])
        process_ids = validated_data.pop('processes', [])  # 工序ID列表，用于后续创建工序

        work_order = WorkOrder.objects.create(**validated_data)

        # 设置图稿（ManyToMany 字段需要在对象创建后设置）
        if artworks:
            work_order.artworks.set(artworks)

        # 设置刀模（ManyToMany 字段需要在对象创建后设置）
        if dies:
            work_order.dies.set(dies)

        # 设置烫金版（ManyToMany 字段需要在对象创建后设置）
        if foiling_plates:
            work_order.foiling_plates.set(foiling_plates)

        # 设置压凸版（ManyToMany 字段需要在对象创建后设置）
        if embossing_plates:
            work_order.embossing_plates.set(embossing_plates)

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

        # 创建关联的物料记录
        if materials_data:
            for item in materials_data:
                WorkOrderMaterial.objects.create(
                    work_order=work_order,
                    material_id=item.get('material'),
                    material_size=item.get('material_size', ''),
                    material_usage=item.get('material_usage', ''),
                    need_cutting=item.get('need_cutting', False),
                    notes=item.get('notes', ''),
                    purchase_status=item.get('purchase_status', 'pending')
                )

        # 自动创建工序（使用用户选择的工序ID列表）
        self._create_work_order_processes(work_order, process_ids=process_ids)

        return work_order

    def update(self, instance, validated_data):
        """更新施工单并处理多个产品和图稿"""
        from rest_framework.exceptions import ValidationError

        # 先 pop 出需要特殊处理的字段
        products_data = validated_data.pop('products_data', None)
        materials_data = validated_data.pop('materials_data', None)
        artworks = validated_data.pop('artworks', None)
        dies = validated_data.pop('dies', None)
        foiling_plates = validated_data.pop('foiling_plates', None)
        embossing_plates = validated_data.pop('embossing_plates', None)
        process_ids = validated_data.pop('processes', None)

        # 如果审核状态为 approved，检查是否尝试修改核心字段
        if instance.approval_status == 'approved':
            request = self.context.get('request')
            if request:
                # 检查用户是否有编辑已审核订单的权限
                can_edit_approved = request.user.has_perm('workorder.change_approved_workorder')

                if not can_edit_approved:
                    # 检查是否尝试修改核心字段
                    modified_protected_fields = []

                    # 检查 ManyToMany 字段（版选择）
                    many_to_many_fields = {
                        'artworks': artworks,
                        'dies': dies,
                        'foiling_plates': foiling_plates,
                        'embossing_plates': embossing_plates,
                    }

                    for field_name, field_value in many_to_many_fields.items():
                        if field_value is not None:
                            old_ids = set(getattr(instance, field_name).values_list('id', flat=True))
                            new_ids = set(field_value or [])
                            if old_ids != new_ids:
                                modified_protected_fields.append(field_name)

                    # 检查产品列表
                    if products_data is not None:
                        old_products = set(instance.products.values_list('id', flat=True))
                        new_products = set([item.get('product') for item in products_data if item.get('product')])
                        if old_products != new_products:
                            modified_protected_fields.append('products')

                    # 检查工序列表
                    if process_ids is not None:
                        old_processes = set(instance.order_processes.values_list('process_id', flat=True))
                        new_processes = set(process_ids or [])
                        if old_processes != new_processes:
                            modified_protected_fields.append('processes')

                    # 检查其他核心字段
                    for field in APPROVED_ORDER_PROTECTED_FIELDS:
                        if field in validated_data:
                            # 跳过已检查的字段
                            if field in ['artworks', 'dies', 'foiling_plates', 'embossing_plates',
                                        'products_data', 'processes']:
                                continue

                            old_value = getattr(instance, field, None)
                            new_value = validated_data[field]

                            if old_value != new_value:
                                modified_protected_fields.append(field)

                    if modified_protected_fields:
                        raise ValidationError({
                            'error': '审核通过后，核心字段（产品、工序、版选择等）不能修改。如需修改，请联系管理员或重新提交审核。',
                            'modified_fields': modified_protected_fields
                        })
                else:
                    # 有权限的用户可以修改核心字段，但需要重新审核
                    instance.approval_status = 'pending'
                    instance.approval_comment = ''

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

        # 如果审核状态是 rejected，修改后自动重置为 pending（允许重新提交审核）
        if instance.approval_status == 'rejected':
            instance.approval_status = 'pending'
            # 清空之前的审核信息，允许重新审核
            instance.approval_comment = ''

        instance.save()

        # 更新刀模（ManyToMany 字段）
        if dies is not None:
            instance.dies.set(dies)

        # 更新烫金版（ManyToMany 字段）
        if foiling_plates is not None:
            instance.foiling_plates.set(foiling_plates)

        # 更新压凸版（ManyToMany 字段）
        if embossing_plates is not None:
            instance.embossing_plates.set(embossing_plates)

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

            # 如果产品列表发生变化，重新创建工序（使用用户选择的工序ID列表）
            # 如果process_ids为空列表，则使用产品的默认工序
            self._recreate_work_order_processes(instance, process_ids=process_ids if process_ids else None)
        elif process_ids is not None:
            # 如果只更新了工序选择，更新工序
            # 如果process_ids为空列表，则使用产品的默认工序
            # 删除现有的未开始工序
            WorkOrderProcess.objects.filter(
                work_order=instance,
                status='pending'
            ).delete()

            # 重新创建工序（如果process_ids为空，则使用产品的默认工序）
            self._create_work_order_processes(instance, process_ids=process_ids if process_ids else None)

        # 如果提供了 materials_data，更新物料列表
        if materials_data is not None:
            # 删除现有物料关联
            WorkOrderMaterial.objects.filter(work_order=instance).delete()

            # 创建新的物料关联
            for item in materials_data:
                WorkOrderMaterial.objects.create(
                    work_order=instance,
                    material_id=item.get('material'),
                    material_size=item.get('material_size', ''),
                    material_usage=item.get('material_usage', ''),
                    need_cutting=item.get('need_cutting', False),
                    notes=item.get('notes', ''),
                    purchase_status=item.get('purchase_status', 'pending')
                )

        return instance

    def _create_work_order_processes(self, work_order, process_ids=None):
        """为施工单自动创建工序"""
        processes = set()

        # 如果提供了 process_ids，使用用户选择的工序
        if process_ids:
            processes.update(Process.objects.filter(id__in=process_ids, is_active=True))
        else:
            # 否则，收集所有产品的默认工序
            for product_item in work_order.products.all():
                processes.update(product_item.product.default_processes.all())

        # 检查是否需要自动添加制版工序
        # 如果施工单中包含图稿、刀模、烫金版或压凸版至少其中一项，自动添加制版工序
        has_artwork = work_order.artworks.exists()
        has_die = work_order.dies.exists()
        has_foiling_plate = work_order.foiling_plates.exists()
        has_embossing_plate = work_order.embossing_plates.exists()

        if has_artwork or has_die or has_foiling_plate or has_embossing_plate:
            # 查找制版工序（使用 code 字段精确匹配）
            plate_making_processes = Process.objects.filter(
                code='CTP',
                is_active=True
            )
            processes.update(plate_making_processes)

        # 为每个工序创建 WorkOrderProcess
        for process in sorted(processes, key=lambda p: p.sort_order):
            # 查找负责该工序的部门（可能有多个，选择第一个）
            departments = Department.objects.filter(processes=process, is_active=True)
            department = departments.first() if departments.exists() else None

            work_order_process, created = WorkOrderProcess.objects.get_or_create(
                work_order=work_order,
                process=process,
                defaults={
                    'department': department,
                    'sequence': process.sort_order
                }
            )

            # 如果是新创建的工序，自动生成草稿任务
            if created:
                work_order_process.generate_draft_tasks()

    def _recreate_work_order_processes(self, work_order, process_ids=None):
        """重新创建施工单的工序（当产品列表变化时）"""
        # 删除现有的工序（如果还没有开始）
        WorkOrderProcess.objects.filter(
            work_order=work_order,
            status='pending'
        ).delete()

        # 重新创建工序（使用用户选择的工序ID列表）
        self._create_work_order_processes(work_order, process_ids=process_ids)


class WorkOrderProcessUpdateSerializer(serializers.ModelSerializer):
    """工序更新序列化器"""

    class Meta:
        model = WorkOrderProcess
        fields = [
            'id', 'status', 'operator', 'actual_start_time',
            'actual_end_time', 'quantity_completed', 'quantity_defective', 'notes'
        ]
