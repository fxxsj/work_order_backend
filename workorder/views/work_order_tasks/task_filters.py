"""
施工单任务过滤器
使用 DjangoFilterBackend 实现高级筛选功能
"""
from django_filters import FilterSet, NumberFilter, CharFilter
from django.db.models import Q
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
    - 施工单号 (work_order_number) - 自定义筛选
    - 任务内容 (work_content) - 模糊搜索
    - 部门名称 (department_name) - 模糊搜索
    """

    # 精确匹配字段
    status = CharFilter(field_name='status')
    task_type = CharFilter(field_name='task_type')
    assigned_department = NumberFilter(field_name='assigned_department')
    assigned_operator = NumberFilter(field_name='assigned_operator')
    work_order_process = NumberFilter(field_name='work_order_process')

    # 自定义筛选：按施工单号搜索
    work_order_number = CharFilter(method='filter_work_order_number')

    # 自定义筛选：按任务内容模糊搜索（与 search_fields 配合）
    work_content = CharFilter(field_name='work_content', lookup_expr='icontains')

    # 自定义筛选：按部门名称搜索
    department_name = CharFilter(field_name='assigned_department__name', lookup_expr='icontains')

    # 自定义筛选：按操作员姓名搜索
    operator_name = CharFilter(method='filter_operator_name')

    # 自定义筛选：草稿任务
    is_draft = CharFilter(method='filter_is_draft')

    class Meta:
        model = WorkOrderTask
        fields = [
            'status', 'task_type', 'assigned_department',
            'assigned_operator', 'work_order_process',
            'work_order_number', 'work_content', 'department_name'
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
            Q(assigned_operator__first_name__icontains=value) |
            Q(assigned_operator__last_name__icontains=value) |
            Q(assigned_operator__username__icontains=value)
        )

    def filter_is_draft(self, queryset, name, value):
        """筛选草稿/正式任务"""
        if value == 'true':
            return queryset.filter(status='draft')
        elif value == 'false':
            return queryset.filter(status__in=['pending', 'in_progress', 'completed', 'cancelled'])
        return queryset
