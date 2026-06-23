"""
核心业务序列化器模块

包含施工单、工序、任务、日志等核心业务的序列化器。
"""

from typing import Any, Dict, List, Optional

from django.db.models import Count, Sum
from rest_framework import serializers

from ..models.assets import ArtworkProduct
from ..models.base import Department, Process
from ..models.core import (
    APPROVED_ORDER_PROTECTED_FIELDS,
    ProcessLog,
    TaskLog,
    WorkOrder,
    WorkOrderMaterial,
    WorkOrderProcess,
    WorkOrderProduct,
    WorkOrderTask,
)
from ..models.products import Product
from ..models.sales import SalesOrderItem
from ..utils import format_color_display
from .base import WorkOrderProductInfoMixin


class ProcessLogSerializer(serializers.ModelSerializer):
    """工序日志序列化器"""

    operator_name = serializers.CharField(
        source="operator.username", read_only=True
    )
    log_type_display = serializers.CharField(
        source="get_log_type_display", read_only=True
    )
    work_order_number = serializers.CharField(
        source="work_order_process.work_order.order_number", read_only=True
    )
    process_name = serializers.CharField(
        source="work_order_process.process.name", read_only=True
    )
    process_code = serializers.CharField(
        source="work_order_process.process.code", read_only=True
    )
    work_order_process_label = serializers.SerializerMethodField()

    class Meta:
        model = ProcessLog
        fields = "__all__"

    def get_work_order_process_label(self, obj) -> Optional[str]:
        """获取施工单工序显示名"""
        if obj.work_order_process:
            return str(obj.work_order_process)
        return None


class TaskLogSerializer(serializers.ModelSerializer):
    """任务操作日志序列化器"""

    log_type_display = serializers.CharField(
        source="get_log_type_display", read_only=True
    )
    operator_name = serializers.SerializerMethodField()
    quantity_increment = serializers.IntegerField(read_only=True)

    class Meta:
        model = TaskLog
        fields = "__all__"

    def get_operator_name(self, obj) -> Optional[str]:
        """获取操作员名称"""
        if obj.operator:
            return obj.operator.username
        return None


class WorkOrderTaskSerializer(serializers.ModelSerializer):
    """施工单任务序列化器"""

    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    is_draft = serializers.SerializerMethodField()
    task_type_display = serializers.CharField(
        source="get_task_type_display", read_only=True
    )
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
    # 开料尺寸/用量（从 WorkOrderMaterial 关联获取）
    material_size = serializers.SerializerMethodField()
    material_usage = serializers.SerializerMethodField()
    # 工序和施工单信息
    work_order_process_info = serializers.SerializerMethodField()
    # 任务操作历史
    logs = TaskLogSerializer(many=True, read_only=True)
    # 分派信息
    assigned_department_name = serializers.CharField(
        source="assigned_department.name", read_only=True, allow_null=True
    )
    assigned_operator_name = serializers.SerializerMethodField()
    # 任务拆分信息
    is_subtask = serializers.SerializerMethodField()
    subtasks_count = serializers.SerializerMethodField()
    parent_task_id = serializers.IntegerField(
        source="parent_task.id", read_only=True, allow_null=True
    )

    class Meta:
        model = WorkOrderTask
        fields = "__all__"
        # 在更新时，某些字段应该是只读的
        read_only_fields = [
            "work_order_process",
            "task_type",
            "work_content",
            "production_quantity",
            "artwork",
            "die",
            "product",
            "material",
            "foiling_plate",
            "embossing_plate",
            "auto_calculate_quantity",
            "created_at",
        ]

    def get_assigned_operator_name(self, obj) -> Optional[str]:
        """获取分派操作员名称"""
        if obj.assigned_operator:
            return (
                f"{obj.assigned_operator.first_name}"
                f"{obj.assigned_operator.last_name}"
            )
        return None

    def get_is_draft(self, obj) -> bool:
        """判断是否为草稿状态"""
        return obj.status == "draft"

    def get_is_subtask(self, obj) -> bool:
        """判断是否为子任务"""
        return obj.is_subtask()

    def get_subtasks_count(self, obj) -> int:
        """获取子任务数量"""
        if obj.pk:
            return obj.subtasks.count()
        return 0

    @staticmethod
    def _related_field(relation_name, field_name, method=False):
        """Generate a get_xxx method for SerializerMethodField."""

        def getter(self, obj):
            related = getattr(obj, relation_name, None)
            if related is None:
                return None
            if method:
                return getattr(related, field_name)()
            return getattr(related, field_name, None)

        return getter

    @staticmethod
    def _add_related_fields(cls, fields_config):
        """Register get_xxx getters in bulk for related code/name pairs."""
        for field_name, relation_name, attr_name, is_method in fields_config:
            setattr(
                cls,
                f"get_{field_name}",
                cls._related_field(relation_name, attr_name, method=is_method),
            )

    def _get_work_order_material(self, obj):
        """获取关联的 WorkOrderMaterial 记录，不存在时返回 None"""
        if not (obj.material and obj.work_order_process):
            return None
        try:
            return WorkOrderMaterial.objects.get(
                work_order=obj.work_order_process.work_order,
                material=obj.material,
            )
        except WorkOrderMaterial.DoesNotExist:
            return None

    def get_material_purchase_status(self, obj) -> Optional[str]:
        """获取物料采购状态"""
        material_record = self._get_work_order_material(obj)
        return material_record.purchase_status if material_record else None

    def get_material_size(self, obj) -> Optional[str]:
        """获取开料尺寸（从 WorkOrderMaterial 关联获取）"""
        material_record = self._get_work_order_material(obj)
        return (
            (material_record.material_size or None)
            if material_record
            else None
        )

    def get_material_usage(self, obj) -> Optional[str]:
        """获取物料用量（从 WorkOrderMaterial 关联获取）"""
        material_record = self._get_work_order_material(obj)
        return (
            (material_record.material_usage or None)
            if material_record
            else None
        )

    def get_work_order_process_info(self, obj) -> Optional[Dict[str, Any]]:
        """获取工序和施工单信息"""
        if obj.work_order_process:
            process = obj.work_order_process.process
            work_order = obj.work_order_process.work_order
            # 获取与工序关联的部门
            departments = []
            if process:
                # 使用反向关系 department_set 来访问关联的部门
                departments = [
                    {"id": dept.id, "name": dept.name, "code": dept.code}
                    for dept in process.department_set.filter(
                        is_active=True
                    ).order_by("sort_order")
                ]
            return {
                "process": {
                    "id": process.id if process else None,
                    "name": process.name if process else None,
                    "code": process.code if process else None,
                    "departments": departments,  # 添加关联的部门列表
                },
                "work_order": {
                    "id": work_order.id if work_order else None,
                    "order_number": (
                        work_order.order_number if work_order else None
                    ),
                    "customer_name": (
                        work_order.customer.name
                        if work_order and work_order.customer
                        else None
                    ),
                    "priority": work_order.priority if work_order else None,
                    "priority_display": (
                        work_order.get_priority_display()
                        if work_order
                        else None
                    ),
                    "delivery_date": (
                        work_order.delivery_date.strftime("%Y-%m-%d")
                        if work_order and work_order.delivery_date
                        else None
                    ),
                },
            }
        return None


WorkOrderTaskSerializer._add_related_fields(
    WorkOrderTaskSerializer,
    [
        ("artwork_code", "artwork", "get_full_code", True),
        ("artwork_name", "artwork", "name", False),
        ("artwork_confirmed", "artwork", "confirmed", False),
        ("die_code", "die", "code", False),
        ("die_name", "die", "name", False),
        ("product_code", "product", "code", False),
        ("product_name", "product", "name", False),
        ("material_code", "material", "code", False),
        ("material_name", "material", "name", False),
        ("foiling_plate_code", "foiling_plate", "code", False),
        ("foiling_plate_name", "foiling_plate", "name", False),
        ("embossing_plate_code", "embossing_plate", "code", False),
        ("embossing_plate_name", "embossing_plate", "name", False),
    ],
)


class TaskAssignmentSerializer(serializers.Serializer):
    """任务分配序列化器"""

    assigned_operator = serializers.IntegerField(
        required=False,
        help_text="分派操作员用户ID",
    )
    assigned_department = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="分派部门ID；为空时清空部门分派",
    )
    notes = serializers.CharField(
        required=False, allow_blank=True, help_text="分配备注"
    )
    reason = serializers.CharField(
        required=False, allow_blank=True, help_text="调整原因"
    )

    def validate(self, attrs):
        assigned_operator = attrs.get("assigned_operator")
        department_provided = "assigned_department" in self.initial_data
        if not assigned_operator and not department_provided:
            raise serializers.ValidationError("请提供操作员ID或分派部门")
        return attrs

    def validate_assigned_operator(self, value):
        """验证操作员ID"""
        from django.contrib.auth.models import User

        if not User.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("指定的操作员不存在或未激活")
        return value


class WorkOrderProcessSerializer(serializers.ModelSerializer):
    """施工单工序序列化器"""

    process_name = serializers.CharField(source="process.name", read_only=True)
    process_code = serializers.CharField(source="process.code", read_only=True)
    operator_name = serializers.CharField(
        source="operator.username", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    department_name = serializers.CharField(
        source="department.name", read_only=True, allow_null=True
    )
    department_code = serializers.CharField(
        source="department.code", read_only=True, allow_null=True
    )
    can_start = serializers.SerializerMethodField()
    logs = ProcessLogSerializer(many=True, read_only=True)
    tasks = WorkOrderTaskSerializer(many=True, read_only=True)

    class Meta:
        model = WorkOrderProcess
        fields = "__all__"

    def get_can_start(self, obj) -> bool:
        """判断工序是否可以开始"""
        return obj.can_start()


class WorkOrderProductSerializer(serializers.ModelSerializer):
    """施工单产品序列化器"""

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    source_type_display = serializers.CharField(
        source="get_source_type_display", read_only=True
    )
    source_sales_order_id = serializers.IntegerField(
        source="sales_order_item.sales_order_id",
        read_only=True,
        allow_null=True,
    )
    source_sales_order_number = serializers.CharField(
        source="sales_order_item.sales_order.order_number",
        read_only=True,
        allow_null=True,
        default=None,
    )
    product_detail = serializers.SerializerMethodField()
    imposition_quantity = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrderProduct
        fields = "__all__"

    def get_product_detail(self, obj) -> Optional[Dict[str, Any]]:
        """获取产品详细信息"""
        from .products import ProductSerializer

        return ProductSerializer(obj.product).data if obj.product else None

    def get_imposition_quantity(self, obj) -> int:
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
                    artwork=artwork, product=obj.product
                ).first()
                if artwork_product:
                    return artwork_product.imposition_quantity
            except Exception:
                continue

        # 如果找不到，返回默认值1
        return 1


class WorkOrderMaterialSerializer(serializers.ModelSerializer):
    """施工单物料序列化器"""

    material_name = serializers.CharField(
        source="material.name", read_only=True
    )
    material_code = serializers.CharField(
        source="material.code", read_only=True
    )
    material_unit = serializers.CharField(
        source="material.unit", read_only=True
    )
    purchase_status_display = serializers.CharField(
        source="get_purchase_status_display", read_only=True
    )

    class Meta:
        model = WorkOrderMaterial
        fields = [
            "id",
            "work_order",
            "material",
            "material_name",
            "material_code",
            "material_unit",
            "material_size",
            "material_usage",
            "need_cutting",
            "notes",
            "purchase_status",
            "purchase_status_display",
            "purchase_date",
            "received_date",
            "cut_date",
            "created_at",
        ]


class WorkOrderListSerializer(
    WorkOrderProductInfoMixin, serializers.ModelSerializer
):
    """施工单列表序列化器（精简版）"""

    customer_name = serializers.CharField(
        source="customer.name", read_only=True
    )
    salesperson_name = serializers.CharField(
        source="customer.salesperson.username", read_only=True, allow_null=True
    )
    manager_name = serializers.CharField(
        source="manager.username", read_only=True, allow_null=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, allow_null=True
    )
    approval_status_display = serializers.CharField(
        source="get_approval_status_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )
    progress_percentage = serializers.SerializerMethodField()
    # 多产品合并显示字段
    product_name = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    total_task_count = serializers.SerializerMethodField()

    # 来源客户订单
    sales_order_id = serializers.IntegerField(read_only=True, allow_null=True)
    sales_order_number = serializers.CharField(
        source="sales_order.order_number", read_only=True, default=None
    )

    class Meta:
        model = WorkOrder
        fields = [
            "id",
            "order_number",
            "customer",
            "customer_name",
            "salesperson_name",
            "product_name",
            "quantity",
            "unit",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "order_date",
            "delivery_date",
            "production_quantity",
            "defective_quantity",
            "total_amount",
            "manager",
            "manager_name",
            "progress_percentage",
            "approval_status",
            "approval_status_display",
            "approved_by_name",
            "approved_at",
            "approval_comment",
            "total_task_count",
            "sales_order_id",
            "sales_order_number",
            "created_at",
        ]


class WorkOrderDetailSerializer(
    WorkOrderProductInfoMixin, serializers.ModelSerializer
):
    """施工单详情序列化器（完整版）"""

    customer_name = serializers.CharField(
        source="customer.name", read_only=True
    )
    customer_detail = serializers.SerializerMethodField()
    product_group_item_display = serializers.SerializerMethodField()
    manager_name = serializers.CharField(
        source="manager.username", read_only=True, allow_null=True
    )
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, allow_null=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, allow_null=True
    )
    approval_status_display = serializers.CharField(
        source="get_approval_status_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    printing_type_display = serializers.CharField(
        source="get_printing_type_display", read_only=True
    )
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
    foiling_plates = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )
    foiling_plate_names = serializers.SerializerMethodField()
    foiling_plate_codes = serializers.SerializerMethodField()
    # 压凸版信息：支持多个压凸版
    embossing_plates = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )
    embossing_plate_names = serializers.SerializerMethodField()
    embossing_plate_codes = serializers.SerializerMethodField()
    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )

    order_processes = WorkOrderProcessSerializer(many=True, read_only=True)
    products = WorkOrderProductSerializer(
        many=True, read_only=True
    )  # 一个施工单包含的多个产品
    materials = WorkOrderMaterialSerializer(many=True, read_only=True)
    # 审核历史记录
    approval_logs = serializers.SerializerMethodField()
    sales_order_numbers = serializers.SerializerMethodField()
    quality_inspection_numbers = serializers.SerializerMethodField()
    invoice_numbers = serializers.SerializerMethodField()
    sales_order_summaries = serializers.SerializerMethodField()
    quality_inspection_summaries = serializers.SerializerMethodField()
    invoice_summaries = serializers.SerializerMethodField()
    sales_order_total_amount = serializers.SerializerMethodField()
    sales_order_paid_amount = serializers.SerializerMethodField()
    sales_order_unpaid_amount = serializers.SerializerMethodField()
    settled_sales_order_count = serializers.SerializerMethodField()
    unsettled_sales_order_count = serializers.SerializerMethodField()
    invoice_count = serializers.SerializerMethodField()
    purchase_order_summaries = serializers.SerializerMethodField()

    progress_percentage = serializers.SerializerMethodField()
    # 多产品合并显示字段（用于基本信息显示）
    product_name = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    total_task_count = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrder
        fields = "__all__"

    EXPAND_GROUPS = {
        "customer": ["customer_detail"],
        "assets": [
            "artwork_names",
            "artwork_codes",
            "artwork_details",
            "artwork_colors",
            "die_names",
            "die_codes",
            "foiling_plate_names",
            "foiling_plate_codes",
            "embossing_plate_names",
            "embossing_plate_codes",
        ],
        "processes": ["order_processes"],
        "products": ["products"],
        "materials": ["materials"],
        "financial": [
            "sales_order_numbers",
            "quality_inspection_numbers",
            "invoice_numbers",
            "sales_order_summaries",
            "quality_inspection_summaries",
            "invoice_summaries",
            "sales_order_total_amount",
            "sales_order_paid_amount",
            "sales_order_unpaid_amount",
            "settled_sales_order_count",
            "unsettled_sales_order_count",
            "invoice_count",
            "purchase_order_summaries",
        ],
        "approval": ["approval_logs"],
        "progress": [
            "progress_percentage",
            "product_name",
            "quantity",
            "unit",
            "total_task_count",
        ],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        expand = self.context.get("expand")
        if expand is None:
            return

        requested = {g.strip() for g in expand.split(",") if g.strip()}
        field_to_group = {}
        for group, fields in self.EXPAND_GROUPS.items():
            for field in fields:
                field_to_group[field] = group

        for field_name in list(self.fields.keys()):
            group = field_to_group.get(field_name)
            if group and group not in requested:
                self.fields.pop(field_name)

    def get_customer_detail(self, obj) -> Optional[Dict[str, Any]]:
        """获取客户详细信息"""
        from .base import CustomerSerializer

        return CustomerSerializer(obj.customer).data if obj.customer else None

    def get_product_group_item_display(self, obj) -> Optional[str]:
        """获取产品组子项显示名称"""
        item = obj.product_group_item
        if not item:
            return None
        group_name = item.product_group.name if item.product_group else None
        product_name = item.product.name if item.product else None
        parts = [
            part for part in [group_name, item.item_name, product_name] if part
        ]
        return " - ".join(parts) if parts else None

    def get_sales_order_numbers(self, obj) -> List[str]:
        """获取来源客户订单号"""
        sales_orders = self._get_sales_orders(obj)
        return [
            sales_order.order_number
            for sales_order in sales_orders
            if sales_order.order_number
        ]

    def get_quality_inspection_numbers(self, obj) -> List[str]:
        """获取关联质检单号"""
        return [
            inspection.inspection_number
            for inspection in obj.quality_inspections.all()
            if inspection.inspection_number
        ]

    def get_invoice_numbers(self, obj) -> List[str]:
        """获取关联发票号"""
        return [
            invoice.invoice_number
            for invoice in obj.invoices.all()
            if invoice.invoice_number
        ]

    def get_sales_order_summaries(self, obj) -> List[Dict[str, Any]]:
        """获取来源客户订单摘要"""
        sales_orders = self._get_sales_orders(obj)
        return [
            {
                "id": sales_order.id,
                "number": sales_order.order_number,
                "status_display": sales_order.get_status_display(),
                "source_label": "客户订单",
                "batch_no": None,
            }
            for sales_order in sales_orders
            if sales_order.order_number
        ]

    def get_quality_inspection_summaries(self, obj) -> List[Dict[str, Any]]:
        """获取关联质检单摘要"""
        return [
            {
                "id": inspection.id,
                "number": inspection.inspection_number,
                "status_display": inspection.get_result_display(),
                "source_label": inspection.get_inspection_type_display(),
                "batch_no": inspection.batch_no or None,
            }
            for inspection in obj.quality_inspections.all()
            if inspection.inspection_number
        ]

    def get_invoice_summaries(self, obj) -> List[Dict[str, Any]]:
        """获取关联发票摘要"""
        return [
            {
                "id": invoice.id,
                "number": invoice.invoice_number,
                "status_display": invoice.get_status_display(),
                "source_label": "财务开票",
                "batch_no": None,
            }
            for invoice in obj.invoices.all()
            if invoice.invoice_number
        ]

    def get_sales_order_total_amount(self, obj) -> float:
        """获取来源客户订单金额合计"""
        return sum(
            float(order.total_amount) for order in self._get_sales_orders(obj)
        )

    def get_sales_order_paid_amount(self, obj) -> float:
        """获取来源客户订单已回款合计"""
        return sum(
            float(order.paid_amount) for order in self._get_sales_orders(obj)
        )

    def get_sales_order_unpaid_amount(self, obj) -> float:
        """获取来源客户订单未回款合计"""
        total = self.get_sales_order_total_amount(obj)
        paid = self.get_sales_order_paid_amount(obj)
        return max(total - paid, 0)

    def get_settled_sales_order_count(self, obj) -> int:
        """获取已结清客户订单数量"""
        return sum(
            1
            for order in self._get_sales_orders(obj)
            if order.payment_status == "paid"
        )

    def get_unsettled_sales_order_count(self, obj) -> int:
        """获取未结清客户订单数量"""
        return sum(
            1
            for order in self._get_sales_orders(obj)
            if order.payment_status != "paid"
        )

    def _get_sales_orders(self, obj):
        return obj.get_related_sales_orders()

    def get_invoice_count(self, obj) -> int:
        """获取关联发票数量"""
        return obj.invoices.count()

    def get_purchase_order_summaries(self, obj) -> List[Dict[str, Any]]:
        """获取关联采购单摘要"""
        if hasattr(obj, "prefetched_purchase_orders"):
            purchase_orders = obj.prefetched_purchase_orders.annotate(
                items_count=Count("items")
            )
        else:
            purchase_orders = (
                obj.purchase_orders.select_related("supplier")
                .annotate(items_count=Count("items"))
                .all()
            )
        return [
            {
                "id": po.id,
                "number": po.order_number,
                "status": po.status,
                "status_display": po.get_status_display(),
                "supplier_name": po.supplier.name if po.supplier else None,
                "total_amount": str(po.total_amount),
                "items_count": po.items_count,
            }
            for po in purchase_orders
        ]

    @staticmethod
    def _m2m_list(relation_name, field_name):
        """Generate a get_xxx method that returns a list of field values
        from a M2M relation."""

        def getter(self, obj):
            manager = getattr(obj, relation_name)
            return [getattr(item, field_name) for item in manager.all()]

        return getter

    @staticmethod
    def _m2m_method_list(relation_name, method_name):
        """Generate a get_xxx method that returns a list of method call
        results from a M2M relation."""

        def getter(self, obj):
            manager = getattr(obj, relation_name)
            return [getattr(item, method_name)() for item in manager.all()]

        return getter

    get_artwork_names = _m2m_list.__func__("artworks", "name")
    get_artwork_codes = _m2m_method_list.__func__("artworks", "get_full_code")

    def get_artwork_details(self, obj) -> List[Dict[str, Any]]:
        """获取图稿详细信息（包含确认状态）"""
        artworks = obj.artworks.all()
        return [
            {
                "id": artwork.id,
                "code": artwork.get_full_code(),
                "name": artwork.name,
                "confirmed": artwork.confirmed,
                "confirmed_by_name": (
                    artwork.confirmed_by.username
                    if artwork.confirmed_by
                    else None
                ),
                "confirmed_at": artwork.confirmed_at,
            }
            for artwork in artworks
        ]

    def get_artwork_colors(self, obj) -> Optional[str]:
        """获取所有图稿的色数信息"""
        artworks = obj.artworks.all()
        if not artworks:
            return None
        color_displays = []
        for artwork in artworks:
            display = format_color_display(
                artwork.cmyk_colors, artwork.other_colors
            )
            if display:
                color_displays.append(display)
        return ", ".join(color_displays) if color_displays else None

    def get_printing_colors_display(self, obj) -> Optional[str]:
        """生成印刷色数显示格式"""
        return format_color_display(
            obj.printing_cmyk_colors, obj.printing_other_colors
        )

    get_die_names = _m2m_list.__func__("dies", "name")
    get_die_codes = _m2m_list.__func__("dies", "code")
    get_foiling_plate_names = _m2m_list.__func__("foiling_plates", "name")
    get_foiling_plate_codes = _m2m_list.__func__("foiling_plates", "code")
    get_embossing_plate_names = _m2m_list.__func__("embossing_plates", "name")
    get_embossing_plate_codes = _m2m_list.__func__("embossing_plates", "code")

    def get_approval_logs(self, obj) -> List[Dict[str, Any]]:
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
        help_text=(
            "产品列表数据，格式：["
            '{"product": id, "quantity": 1, "unit": "件", '
            '"specification": "", "sort_order": 0}]'
        ),
    )
    # 支持物料列表（与施工单一起创建）
    materials_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text=(
            "物料列表数据，格式：["
            '{"material": id, "material_size": "", '
            '"material_usage": "", "need_cutting": false, "notes": ""}]'
        ),
    )
    # 工序ID列表（用于验证版的选择）
    # 使用自定义方法来过滤 null 值
    processes = serializers.ListField(
        child=serializers.IntegerField(
            allow_null=True
        ),  # 允许 null，然后在 validate 中过滤
        required=False,
        allow_empty=True,
        help_text="选中的工序ID列表，用于验证版的选择",
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
            "id",
            "order_number",
            "customer",
            "sales_order",
            "status",
            "priority",
            "order_date",
            "delivery_date",
            "actual_delivery_date",
            "production_quantity",
            "defective_quantity",
            "total_amount",
            "design_file",
            "notes",
            "artworks",
            "dies",
            "foiling_plates",
            "embossing_plates",
            "printing_type",
            "printing_cmyk_colors",
            "printing_other_colors",
            "products_data",
            "materials_data",
            "processes",
        ]
        read_only_fields = ["order_number"]

    def validate(self, data):
        """验证数据，根据工序验证版的选择。"""
        instance = getattr(self, "instance", None)
        sales_order = data.get(
            "sales_order", getattr(instance, "sales_order", None)
        )
        products_data = data.get("products_data", [])
        artworks = data.get("artworks")
        dies = data.get("dies")
        foiling_plates = data.get("foiling_plates")
        embossing_plates = data.get("embossing_plates")
        process_ids = data.get("processes", [])

        if sales_order is not None:
            data = self._validate_sales_order_consistency(data, sales_order)

        validated_products_data = self._validate_products_data(
            products_data, sales_order, instance
        )
        if validated_products_data:
            data["products_data"] = validated_products_data
            products_data = validated_products_data

        if process_ids:
            processes = Process.objects.filter(
                id__in=process_ids, is_active=True
            )
            self._validate_plate_requirements(
                processes,
                instance,
                artworks,
                dies,
                foiling_plates,
                embossing_plates,
            )

        if "artworks" in data:
            data = self._normalize_printing_type(data, artworks)

        if products_data:
            data["total_amount"] = self._compute_total_amount(
                products_data, data.get("total_amount")
            )

        return data

    def _validate_sales_order_consistency(self, data, sales_order):
        """当存在客户订单时，校验并补齐客户、日期、金额等字段。"""
        customer = data.get("customer")
        if customer is None:
            data["customer"] = sales_order.customer
        elif customer.id != sales_order.customer_id:
            raise serializers.ValidationError(
                {"customer": "所选客户订单与当前客户不一致，请重新选择"}
            )

        if not data.get("order_date"):
            data["order_date"] = sales_order.order_date
        if not data.get("delivery_date"):
            data["delivery_date"] = sales_order.delivery_date

        products_data = data.get("products_data", [])
        if not products_data and not data.get("total_amount"):
            data["total_amount"] = sales_order.total_amount

        return data

    def _validate_products_data(self, products_data, sales_order, instance):
        """校验并规范化 products_data，返回规范化后的列表。"""
        if not products_data:
            return []

        validated_products_data = []
        requested_quantities_by_sales_item = {}

        for index, item in enumerate(products_data, start=1):
            if not isinstance(item, dict):
                raise serializers.ValidationError(
                    {"products_data": f"第 {index} 个产品配置无效"}
                )

            normalized_item = dict(item)
            source_type = normalized_item.get("source_type") or "stock"
            normalized_item["source_type"] = source_type
            sales_order_item_id = normalized_item.get("sales_order_item")

            if source_type == "sales_order":
                if not sales_order_item_id:
                    raise serializers.ValidationError(
                        {
                            "products_data": (
                                f"第 {index} 个产品来源为客户订单时，"
                                f"必须选择来源订单明细"
                            )
                        }
                    )

                try:
                    sales_order_item = SalesOrderItem.objects.select_related(
                        "sales_order", "product"
                    ).get(id=sales_order_item_id)
                except SalesOrderItem.DoesNotExist as exc:
                    raise serializers.ValidationError(
                        {"products_data": f"第 {index} 个来源订单明细不存在"}
                    ) from exc

                product_id = normalized_item.get("product")
                if not product_id:
                    normalized_item["product"] = sales_order_item.product_id
                elif int(product_id) != sales_order_item.product_id:
                    raise serializers.ValidationError(
                        {
                            "products_data": f"第 {index} 个产品与来源订单明细中的产品不一致"
                        }
                    )

                if not normalized_item.get("unit"):
                    normalized_item["unit"] = sales_order_item.unit or "件"

                try:
                    quantity = int(normalized_item.get("quantity") or 0)
                except (TypeError, ValueError) as exc:
                    raise serializers.ValidationError(
                        {"products_data": f"第 {index} 个产品数量无效"}
                    ) from exc
                if quantity <= 0:
                    raise serializers.ValidationError(
                        {"products_data": f"第 {index} 个产品数量必须大于 0"}
                    )

                requested_quantities_by_sales_item[sales_order_item.id] = (
                    requested_quantities_by_sales_item.get(
                        sales_order_item.id, 0
                    )
                    + quantity
                )
            else:
                normalized_item["sales_order_item"] = None

            validated_products_data.append(normalized_item)

        if requested_quantities_by_sales_item:
            self._validate_sales_order_item_quantities(
                requested_quantities_by_sales_item, instance
            )

        return validated_products_data

    def _validate_sales_order_item_quantities(
        self, requested_quantities_by_sales_item, instance
    ):
        """校验客户订单明细的剩余可开数量是否足够。"""
        sales_order_item_ids = list(requested_quantities_by_sales_item.keys())
        allocated_queryset = WorkOrderProduct.objects.filter(
            sales_order_item_id__in=sales_order_item_ids,
            source_type="sales_order",
        )
        if instance is not None:
            allocated_queryset = allocated_queryset.exclude(
                work_order=instance
            )

        allocated_totals = {
            item["sales_order_item_id"]: item["total_quantity"] or 0
            for item in allocated_queryset.values(
                "sales_order_item_id"
            ).annotate(total_quantity=Sum("quantity"))
        }

        sales_order_items = {
            item.id: item
            for item in SalesOrderItem.objects.filter(
                id__in=sales_order_item_ids
            )
        }
        for (
            sales_order_item_id,
            requested_quantity,
        ) in requested_quantities_by_sales_item.items():
            sales_order_item = sales_order_items.get(sales_order_item_id)
            if sales_order_item is None:
                raise serializers.ValidationError(
                    {"products_data": "来源订单明细不存在"}
                )
            allocated_quantity = int(
                allocated_totals.get(sales_order_item_id, 0) or 0
            )
            remaining_quantity = max(
                int(sales_order_item.quantity) - allocated_quantity,
                0,
            )
            if requested_quantity > remaining_quantity:
                raise serializers.ValidationError(
                    {
                        "products_data": (
                            f"{sales_order_item.product.name} 来源订单明细剩余可开数量为 "
                            f"{remaining_quantity}，当前提交了 {requested_quantity}"
                        )
                    }
                )

    def _validate_plate_requirements(
        self,
        processes,
        instance,
        artworks,
        dies,
        foiling_plates,
        embossing_plates,
    ):
        """根据选中工序校验图稿/刀模/烫金版/压凸版是否已选择。"""
        self._validate_plate_requirement(
            processes,
            instance,
            artworks,
            relation_name="artworks",
            process_filter_field="requires_artwork",
            required_filter_field="artwork_required",
            error_field_name="artworks",
            error_message_template="选择了需要图稿的工序（{process_names}），请至少选择一个图稿",
        )
        self._validate_plate_requirement(
            processes,
            instance,
            dies,
            relation_name="dies",
            process_filter_field="requires_die",
            required_filter_field="die_required",
            error_field_name="dies",
            error_message_template="选择了需要刀模的工序（{process_names}），请至少选择一个刀模",
        )
        self._validate_plate_requirement(
            processes,
            instance,
            foiling_plates,
            relation_name="foiling_plates",
            process_filter_field="requires_foiling_plate",
            required_filter_field="foiling_plate_required",
            error_field_name="foiling_plates",
            error_message_template="选择了需要烫金版的工序（{process_names}），请至少选择一个烫金版",
        )
        self._validate_plate_requirement(
            processes,
            instance,
            embossing_plates,
            relation_name="embossing_plates",
            process_filter_field="requires_embossing_plate",
            required_filter_field="embossing_plate_required",
            error_field_name="embossing_plates",
            error_message_template="选择了需要压凸版的工序（{process_names}），请至少选择一个压凸版",
        )

    def _normalize_printing_type(self, data, artworks):
        """根据 artworks 选择情况规范化 printing_type。"""
        artworks_value = artworks if artworks is not None else []
        if not artworks_value or len(artworks_value) == 0:
            data["printing_type"] = "none"
        elif data.get("printing_type") == "none":
            data["printing_type"] = "front"
        return data

    def _compute_total_amount(self, products_data, current_total):
        """根据产品列表计算总金额；若无有效金额则保留当前值。"""
        total = 0
        for item in products_data:
            product_id = item.get("product")
            if product_id:
                try:
                    product_obj = Product.objects.get(id=product_id)
                    quantity = item.get("quantity", 1)
                    total += product_obj.unit_price * quantity
                except Product.DoesNotExist:
                    pass
        return total if total > 0 else current_total

    def create(self, validated_data):
        """创建施工单并处理多个产品和图稿"""
        products_data = validated_data.pop("products_data", [])
        materials_data = validated_data.pop("materials_data", [])
        artworks = validated_data.pop("artworks", [])
        dies = validated_data.pop("dies", [])
        foiling_plates = validated_data.pop("foiling_plates", [])
        embossing_plates = validated_data.pop("embossing_plates", [])
        process_ids = validated_data.pop(
            "processes", []
        )  # 工序ID列表，用于后续创建工序

        work_order = WorkOrder.objects.create(**validated_data)

        # 设置 M2M 关系
        self._sync_many_to_many(
            work_order,
            artworks=artworks,
            dies=dies,
            foiling_plates=foiling_plates,
            embossing_plates=embossing_plates,
        )

        # 创建关联的产品记录
        self._sync_products(work_order, products_data)

        # 创建关联的物料记录
        self._sync_materials(work_order, materials_data)

        # 自动创建工序（使用用户选择的工序ID列表）
        self._create_work_order_processes(work_order, process_ids=process_ids)

        return work_order

    def update(self, instance, validated_data):
        """更新施工单并处理多个产品和图稿"""
        from rest_framework.exceptions import ValidationError

        # 先 pop 出需要特殊处理的字段
        products_data = validated_data.pop("products_data", None)
        materials_data = validated_data.pop("materials_data", None)
        artworks = validated_data.pop("artworks", None)
        dies = validated_data.pop("dies", None)
        foiling_plates = validated_data.pop("foiling_plates", None)
        embossing_plates = validated_data.pop("embossing_plates", None)
        process_ids = validated_data.pop("processes", None)

        # 如果审核状态为 approved，检查是否尝试修改核心字段
        if instance.approval_status == "approved":
            request = self.context.get("request")
            if request:
                # 检查用户是否有编辑已审核订单的权限
                can_edit_approved = request.user.has_perm(
                    "workorder.change_approved_workorder"
                )

                if not can_edit_approved:
                    # 检查是否尝试修改核心字段
                    modified_protected_fields = (
                        self._get_modified_protected_m2m_fields(
                            instance,
                            artworks,
                            dies,
                            foiling_plates,
                            embossing_plates,
                        )
                    )

                    # 检查产品列表
                    if products_data is not None:
                        old_products = set(
                            instance.products.values_list("id", flat=True)
                        )
                        new_products = set(
                            [
                                item.get("product")
                                for item in products_data
                                if item.get("product")
                            ]
                        )
                        if old_products != new_products:
                            modified_protected_fields.append("products")

                    # 检查工序列表
                    if process_ids is not None:
                        old_processes = set(
                            instance.order_processes.values_list(
                                "process_id", flat=True
                            )
                        )
                        new_processes = set(process_ids or [])
                        if old_processes != new_processes:
                            modified_protected_fields.append("processes")

                    # 检查其他核心字段
                    for field in APPROVED_ORDER_PROTECTED_FIELDS:
                        if field in validated_data:
                            # 跳过已检查的字段
                            if field in [
                                "artworks",
                                "dies",
                                "foiling_plates",
                                "embossing_plates",
                                "products_data",
                                "processes",
                            ]:
                                continue

                            old_value = getattr(instance, field, None)
                            new_value = validated_data[field]

                            if old_value != new_value:
                                modified_protected_fields.append(field)

                    if modified_protected_fields:
                        raise ValidationError(
                            {
                                "error": (
                                    "审核通过后，核心字段（产品、工序、版选择等）"
                                    "不能修改。如需修改，请联系管理员或重新提交审核。"
                                ),
                                "modified_fields": modified_protected_fields,
                            }
                        )
                else:
                    # 有权限的用户可以修改核心字段，但需要重新审核
                    instance.approval_status = "submitted"
                    instance.approval_comment = ""

        # 根据 artworks 调整印刷形式
        if artworks is not None:
            if not artworks or len(artworks) == 0:
                validated_data["printing_type"] = "none"
            elif validated_data.get("printing_type") == "none":
                # 如果选择了图稿但印刷形式是"不需要印刷"，默认改为"正面印刷"
                validated_data["printing_type"] = "front"

        # 更新 M2M 关系
        self._sync_many_to_many(
            instance,
            artworks=artworks,
            dies=dies,
            foiling_plates=foiling_plates,
            embossing_plates=embossing_plates,
        )

        # 更新施工单基本信息
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # 如果审核状态是 rejected，修改后回到草稿，用户明确提交后再进入待审核。
        if instance.approval_status == "rejected":
            instance.approval_status = "draft"
            # 清空之前的审核信息，允许重新审核
            instance.approval_comment = ""

        instance.save()

        # 如果提供了 products_data，更新产品列表
        if products_data is not None:
            self._sync_products(instance, products_data)

            # 如果产品列表发生变化，重新创建工序（使用用户选择的工序ID列表）
            # 如果process_ids为空列表，则使用产品的默认工序
            self._recreate_work_order_processes(
                instance, process_ids=process_ids if process_ids else None
            )
        elif process_ids is not None:
            # 如果只更新了工序选择，更新工序
            # 如果process_ids为空列表，则使用产品的默认工序
            # 删除现有的未开始工序
            WorkOrderProcess.objects.filter(
                work_order=instance, status="pending"
            ).delete()

            # 重新创建工序（如果process_ids为空，则使用产品的默认工序）
            self._create_work_order_processes(
                instance,
                process_ids=process_ids if process_ids is not None else None,
            )

        # 如果提供了 materials_data，更新物料列表
        if materials_data is not None:
            self._sync_materials(instance, materials_data)

        return instance

    def _create_work_order_processes(self, work_order, process_ids=None):
        """为施工单自动创建工序"""
        processes = set()

        # 如果提供了 process_ids，使用用户选择的工序
        if process_ids:
            processes.update(
                Process.objects.filter(id__in=process_ids, is_active=True)
            )
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
                code="CTP", is_active=True
            )
            processes.update(plate_making_processes)

        # 为每个工序创建 WorkOrderProcess
        from workorder.models.system import TaskAssignmentRule

        for process in sorted(processes, key=lambda p: p.sort_order):
            # 部门分配优先级：
            # 1. TaskAssignmentRule 中该工序优先级最高的部门
            # 2. 兜底：M2M processes 关联的第一个部门
            assignment_rule = (
                TaskAssignmentRule.objects.filter(
                    process=process, is_active=True
                )
                .select_related("department")
                .order_by("-priority")
                .first()
            )
            if assignment_rule:
                department = assignment_rule.department
            else:
                departments = Department.objects.filter(
                    processes=process, is_active=True
                )
                department = (
                    departments.first() if departments.exists() else None
                )

            WorkOrderProcess.objects.get_or_create(
                work_order=work_order,
                process=process,
                defaults={
                    "department": department,
                    "sequence": process.sort_order,
                },
            )

    def _recreate_work_order_processes(self, work_order, process_ids=None):
        """重新创建施工单的工序（当产品列表变化时）"""
        # 删除现有的工序（如果还没有开始）
        WorkOrderProcess.objects.filter(
            work_order=work_order, status="pending"
        ).delete()

        # 重新创建工序（使用用户选择的工序ID列表）
        self._create_work_order_processes(work_order, process_ids=process_ids)

    # --- 辅助方法：校验与同步 ---

    def _get_plate_value_to_check(self, instance, sent_values, relation_name):
        """获取用于校验的版值：优先使用发送值，否则回退到数据库当前值。"""
        if sent_values is not None:
            return sent_values
        if instance:
            return list(
                getattr(instance, relation_name).values_list("id", flat=True)
            )
        return []

    def _validate_plate_requirement(
        self,
        processes,
        instance,
        sent_values,
        relation_name,
        process_filter_field,
        required_filter_field,
        error_field_name,
        error_message_template,
    ):
        """校验选中工序是否要求某种版，且必须至少选择一项。"""
        processes_requiring = processes.filter(**{process_filter_field: True})
        if not processes_requiring.exists():
            return

        mandatory = processes_requiring.filter(**{required_filter_field: True})
        if not mandatory.exists():
            return

        values_to_check = self._get_plate_value_to_check(
            instance, sent_values, relation_name
        )
        if not values_to_check or len(values_to_check) == 0:
            process_names = ", ".join([p.name for p in mandatory])
            raise serializers.ValidationError(
                {
                    error_field_name: error_message_template.format(
                        process_names=process_names
                    )
                }
            )

    def _sync_many_to_many(
        self,
        instance,
        *,
        artworks=None,
        dies=None,
        foiling_plates=None,
        embossing_plates=None,
    ):
        """同步施工单的 M2M 版关系。仅当对应字段被发送（不为 None）时才更新。"""
        if artworks is not None:
            instance.artworks.set(artworks)
        if dies is not None:
            instance.dies.set(dies)
        if foiling_plates is not None:
            instance.foiling_plates.set(foiling_plates)
        if embossing_plates is not None:
            instance.embossing_plates.set(embossing_plates)

    def _sync_products(self, work_order, products_data):
        """同步施工单产品：删除旧记录并重建。"""
        if products_data is None:
            return
        WorkOrderProduct.objects.filter(work_order=work_order).delete()
        for item in products_data:
            WorkOrderProduct.objects.create(
                work_order=work_order,
                product_id=item.get("product"),
                quantity=item.get("quantity", 1),
                unit=item.get("unit", "件"),
                specification=item.get("specification", ""),
                source_type=item.get("source_type", "stock"),
                sales_order_item_id=item.get("sales_order_item"),
                sort_order=item.get("sort_order", 0),
            )

    def _sync_materials(self, work_order, materials_data):
        """同步施工单物料：删除旧记录并重建。"""
        if materials_data is None:
            return
        WorkOrderMaterial.objects.filter(work_order=work_order).delete()
        for item in materials_data:
            WorkOrderMaterial.objects.create(
                work_order=work_order,
                material_id=item.get("material"),
                material_size=item.get("material_size", ""),
                material_usage=item.get("material_usage", ""),
                need_cutting=item.get("need_cutting", False),
                notes=item.get("notes", ""),
                purchase_status=item.get("purchase_status", "pending"),
            )

    def _get_modified_protected_m2m_fields(
        self, instance, artworks, dies, foiling_plates, embossing_plates
    ):
        """检查已审核施工单的 M2M 版字段是否被修改。"""
        modified = []
        many_to_many_fields = {
            "artworks": artworks,
            "dies": dies,
            "foiling_plates": foiling_plates,
            "embossing_plates": embossing_plates,
        }
        for field_name, field_value in many_to_many_fields.items():
            if field_value is not None:
                old_ids = set(
                    getattr(instance, field_name).values_list("id", flat=True)
                )
                new_ids = set(field_value or [])
                if old_ids != new_ids:
                    modified.append(field_name)
        return modified


class WorkOrderProcessUpdateSerializer(serializers.ModelSerializer):
    """工序更新序列化器"""

    class Meta:
        model = WorkOrderProcess
        fields = [
            "id",
            "status",
            "operator",
            "actual_start_time",
            "actual_end_time",
            "quantity_completed",
            "quantity_defective",
            "notes",
        ]
