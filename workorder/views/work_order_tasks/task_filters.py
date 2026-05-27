"""
施工单任务过滤器
使用 DjangoFilterBackend 实现高级筛选功能
"""

from django.db.models import Q
from django_filters import BooleanFilter, CharFilter, DateFilter, FilterSet, NumberFilter

from workorder.models.core import WorkOrderTask


class WorkOrderTaskFilterSet(FilterSet):
    """
    施工单任务筛选器

    支持按以下维度筛选：
    - 状态 (status)
    - 任务类型 (task_type)
    - 分派部门 (assigned_department)
    - 分派操作员 (assigned_operator)
    - 工序 (work_order_process)
    - 工序主数据 (process)
    - 施工单号 (work_order_number) - 自定义筛选
    - 任务内容 (work_content) - 模糊搜索
    - 部门名称 (department_name) - 模糊搜索
    - 客户名称 (customer_name) - 模糊搜索
    - 日期/数量范围
    """

    # 精确匹配字段
    status = CharFilter(field_name="status")
    task_type = CharFilter(field_name="task_type")
    assigned_department = NumberFilter(field_name="assigned_department")
    assigned_operator = NumberFilter(field_name="assigned_operator")
    work_order_process = NumberFilter(field_name="work_order_process")
    process = NumberFilter(field_name="work_order_process__process")
    product = NumberFilter(field_name="product")
    material = NumberFilter(field_name="material")

    # 自定义筛选：按施工单号搜索
    work_order_number = CharFilter(method="filter_work_order_number")

    # 自定义筛选：按任务内容模糊搜索（与 search_fields 配合）
    work_content = CharFilter(field_name="work_content", lookup_expr="icontains")

    # 自定义筛选：按部门名称搜索
    department_name = CharFilter(
        field_name="assigned_department__name", lookup_expr="icontains"
    )

    # 自定义筛选：按操作员姓名搜索
    operator_name = CharFilter(method="filter_operator_name")

    # 关联筛选：按施工单优先级筛选
    priority = CharFilter(field_name="work_order_process__work_order__priority")
    customer_name = CharFilter(
        field_name="work_order_process__work_order__customer__name",
        lookup_expr="icontains",
    )
    delivery_date_after = DateFilter(
        field_name="work_order_process__work_order__delivery_date",
        lookup_expr="gte",
    )
    delivery_date_before = DateFilter(
        field_name="work_order_process__work_order__delivery_date",
        lookup_expr="lte",
    )
    created_at_after = DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_at_before = DateFilter(field_name="created_at", lookup_expr="date__lte")
    production_quantity_min = NumberFilter(
        field_name="production_quantity", lookup_expr="gte"
    )
    production_quantity_max = NumberFilter(
        field_name="production_quantity", lookup_expr="lte"
    )
    quantity_completed_min = NumberFilter(
        field_name="quantity_completed", lookup_expr="gte"
    )
    quantity_completed_max = NumberFilter(
        field_name="quantity_completed", lookup_expr="lte"
    )
    is_draft = BooleanFilter(method="filter_is_draft")

    class Meta:
        model = WorkOrderTask
        fields = [
            "status",
            "task_type",
            "assigned_department",
            "assigned_operator",
            "work_order_process",
            "process",
            "product",
            "material",
            "work_order_number",
            "work_content",
            "department_name",
            "operator_name",
            "priority",
            "customer_name",
            "delivery_date_after",
            "delivery_date_before",
            "created_at_after",
            "created_at_before",
            "production_quantity_min",
            "production_quantity_max",
            "quantity_completed_min",
            "quantity_completed_max",
            "is_draft",
        ]

    def filter_work_order_number(self, queryset, name, value):
        """按施工单号搜索"""
        if not value:
            return queryset
        return queryset.filter(
            work_order_process__work_order__order_number__icontains=value
        )

    def filter_operator_name(self, queryset, name, value):
        """按操作员姓名搜索"""
        if not value:
            return queryset
        return queryset.filter(
            Q(assigned_operator__first_name__icontains=value)
            | Q(assigned_operator__last_name__icontains=value)
            | Q(assigned_operator__username__icontains=value)
        )

    def filter_is_draft(self, queryset, name, value):
        """筛选草稿/正式任务"""
        if value is True:
            return queryset.filter(status="draft")
        elif value is False:
            return queryset.filter(
                status__in=["pending", "in_progress", "completed", "cancelled"]
            )
        return queryset
