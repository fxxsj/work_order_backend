"""
施工单任务视图集模块

将原始的 work_order_tasks.py 拆分为多个模块以提高可维护性。

拆分后的文件结构：
- task_main.py: 基础 ViewSet 配置
- task_actions.py: 单个任务操作
- task_bulk.py: 批量操作
- task_stats.py: 统计和导出
"""

# 导入各个模块
from .task_main import BaseWorkOrderTaskViewSet
from .task_actions import TaskActionsMixin
from .task_bulk import TaskBulkMixin
from .task_stats import TaskStatsMixin

# 组合所有 Mixin 成完整的 ViewSet
# 注意：Mixin 的顺序很重要！
# 从最底层到最高层：
# 1. BaseWorkOrderTaskViewSet - 基础 CRUD
# 2. TaskActionsMixin - 单个任务操作
# 3. TaskBulkMixin - 批量操作
# 4. TaskStatsMixin - 统计和导出
class WorkOrderTaskViewSet(
    TaskStatsMixin,
    TaskBulkMixin,
    TaskActionsMixin,
    BaseWorkOrderTaskViewSet
):
    """
    完整的施工单任务视图集
    
    通过组合多个 Mixin 实现，每个 Mixin 提供特定的功能：
    - BaseWorkOrderTaskViewSet: 基础的 CRUD 操作和权限控制
    - TaskActionsMixin: 单个任务的操作（更新数量、完成、拆分、分派、取消）
    - TaskBulkMixin: 批量操作（批量更新、批量完成、批量取消、批量分派）
    - TaskStatsMixin: 统计查询和导出功能
    
    MRO (Method Resolution Order):
    WorkOrderTaskViewSet -> TaskStatsMixin -> TaskBulkMixin -> TaskActionsMixin -> BaseWorkOrderTaskViewSet
    """
    pass

# 保持向后兼容：导出相同的类名
__all__ = ['WorkOrderTaskViewSet']
