"""
任务分派服务

提供任务分派预览和自动分派功能：
- DispatchPreviewService: 提供分派规则预览
- AutoDispatchService: 提供基于优先级规则的自动分派
"""
from typing import Dict, List, Optional
from django.db.models import Count, Q
from django.core.cache import cache
from ..models.system import TaskAssignmentRule
from ..models.core import WorkOrderTask


class DispatchPreviewService:
    """任务分派预览服务

    提供基于当前优先级规则的任务分派预览功能
    """

    @staticmethod
    def generate_preview() -> List[Dict]:
        """生成所有活跃工序的分派预览

        Returns:
            包含工序信息和目标部门的字典列表
            每个字典包含:
            - process_id: 工序ID
            - process_name: 工序名称
            - process_code: 工序编码
            - target_department_id: 目标部门ID
            - target_department_name: 目标部门名称
            - current_load: 当前部门负载（pending + in_progress任务数）
            - priority: 优先级
            - is_active: 是否启用
        """
        from ..models.base import Process

        # 获取所有活跃工序
        processes = Process.objects.filter(is_active=True).order_by('code')
        preview_data = []

        for process in processes:
            # 获取该工序下优先级最高的活跃规则
            rule = TaskAssignmentRule.objects.filter(
                process=process,
                is_active=True
            ).select_related('department').order_by('-priority').first()

            if rule:
                # 计算目标部门的当前负载（待处理 + 进行中的任务）
                dept_load = WorkOrderTask.objects.filter(
                    assigned_department=rule.department,
                    status__in=['pending', 'in_progress']
                ).count()

                preview_data.append({
                    'process_id': process.id,
                    'process_name': process.name,
                    'process_code': process.code,
                    'target_department_id': rule.department.id,
                    'target_department_name': rule.department.name,
                    'current_load': dept_load,
                    'priority': rule.priority,
                    'is_active': rule.is_active,
                    'operator_selection_strategy': rule.operator_selection_strategy
                })

        return preview_data

    @staticmethod
    def simulate_dispatch(process_id: int) -> Dict:
        """模拟指定工序的任务分派

        Args:
            process_id: 工序ID

        Returns:
            包含目标部门和负载信息的字典
            {
                'process': 工序名称,
                'target_department': 目标部门名称,
                'priority': 优先级,
                'current_load': 当前负载,
                'selection_strategy': 操作员选择策略,
                'all_rules': 该工序的所有规则列表（按优先级排序）
            }
            或 {'error': 错误信息}
        """
        from ..models.base import Process

        try:
            process = Process.objects.get(id=process_id)
        except Process.DoesNotExist:
            return {'error': f'工序ID {process_id} 不存在'}

        # 获取该工序的所有活跃规则，按优先级降序排列
        rules = TaskAssignmentRule.objects.filter(
            process=process,
            is_active=True
        ).select_related('department').order_by('-priority')

        if not rules.exists():
            return {
                'error': f'工序"{process.name}"没有配置活跃的分派规则',
                'process_id': process_id,
                'process_name': process.name
            }

        # 返回优先级最高的规则
        top_rule = rules.first()
        dept_load = WorkOrderTask.objects.filter(
            assigned_department=top_rule.department,
            status__in=['pending', 'in_progress']
        ).count()

        # 收集所有规则信息
        all_rules = []
        for rule in rules:
            rule_load = WorkOrderTask.objects.filter(
                assigned_department=rule.department,
                status__in=['pending', 'in_progress']
            ).count()
            all_rules.append({
                'department_id': rule.department.id,
                'department_name': rule.department.name,
                'priority': rule.priority,
                'current_load': rule_load,
                'is_active': rule.is_active,
                'selection_strategy': rule.operator_selection_strategy
            })

        return {
            'process_id': process.id,
            'process_name': process.name,
            'process_code': process.code,
            'target_department_id': top_rule.department.id,
            'target_department_name': top_rule.department.name,
            'priority': top_rule.priority,
            'current_load': dept_load,
            'selection_strategy': top_rule.operator_selection_strategy,
            'all_rules': all_rules
        }


class AutoDispatchService:
    """自动分派服务

    基于配置的优先级规则自动将任务分派到部门
    """

    @staticmethod
    def is_global_dispatch_enabled() -> bool:
        """检查全局自动分派是否启用

        Returns:
            bool: True 表示已启用，False 表示未启用（默认）
        """
        return cache.get('dispatch_global_enabled', False)

    @staticmethod
    def set_global_dispatch_enabled(enabled: bool) -> bool:
        """设置全局自动分派启用状态

        Args:
            enabled: True 启用，False 禁用

        Returns:
            bool: 新的状态
        """
        cache.set('dispatch_global_enabled', enabled, timeout=None)
        return enabled

    @staticmethod
    def dispatch_task(task, process=None) -> Optional['Department']:
        """根据优先级规则自动分派任务到部门

        分派逻辑：
        1. 检查全局分派开关，如果禁用则返回 None
        2. 如果未提供 process，从 task.work_order_process 获取
        3. 查询该工序的活跃分派规则（按优先级降序）
        4. 验证规则的部门是否在该工序的可用部门列表中
        5. 返回第一个匹配的部门，如果都不匹配则返回 None

        Args:
            task: WorkOrderTask 实例
            process: Process 实例（可选，默认从 task 获取）

        Returns:
            Department: 分派的部门对象，如果未分派则返回 None
        """
        from ..models.base import Department

        # 检查全局分派开关
        if not AutoDispatchService.is_global_dispatch_enabled():
            return None

        # 获取工序
        if not process:
            if not task.work_order_process:
                return None
            process = task.work_order_process.process

        if not process:
            return None

        # 查询该工序的活跃分派规则，按优先级降序排列
        rules = TaskAssignmentRule.objects.filter(
            process=process,
            is_active=True
        ).select_related('department').order_by('-priority')

        if not rules.exists():
            # 没有配置规则，返回 None（调用方使用兜底逻辑）
            return None

        # 获取工序的可用部门列表
        available_departments = Department.objects.filter(
            processes=process,
            is_active=True
        )

        if not available_departments.exists():
            # 工序没有可用部门
            return None

        # 按优先级检查每个规则
        for rule in rules:
            if rule.department in available_departments:
                # 找到第一个匹配的部门
                return rule.department
            else:
                # 规则的部门不在可用列表中，记录日志并跳过
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"分派规则跳过：工序 {process.name} 的规则部门 "
                    f"{rule.department.name} 不在该工序的可用部门列表中"
                )

        # 所有规则的部门都不在可用列表中，返回 None
        return None

    @staticmethod
    def get_highest_priority_department(process) -> Optional['Department']:
        """获取工序的优先级最高的活跃规则对应的部门

        Args:
            process: Process 实例

        Returns:
            Department: 优先级最高的部门，如果没有规则则返回 None
        """
        rule = TaskAssignmentRule.objects.filter(
            process=process,
            is_active=True
        ).select_related('department').order_by('-priority').first()

        if rule:
            return rule.department
        return None

    @staticmethod
    def is_department_available_for_process(department, process) -> bool:
        """检查部门是否可以处理指定工序

        Args:
            department: Department 实例
            process: Process 实例

        Returns:
            bool: True 表示部门可以处理该工序
        """
        from ..models.base import Department

        return Department.objects.filter(
            id=department.id,
            processes=process,
            is_active=True
        ).exists()
