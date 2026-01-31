"""
任务分派预览服务

提供任务分派规则预览功能，用于配置界面展示分派效果。
"""
from typing import Dict, List
from django.db.models import Count, Q
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
