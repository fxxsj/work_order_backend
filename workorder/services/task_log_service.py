"""
任务日志服务

提供任务分派历史查询等业务逻辑。
"""

from datetime import datetime, timedelta

from django.db.models import Q

from workorder.models.core import TaskLog
from workorder.serializers.core import TaskLogSerializer


class TaskLogService:
    """任务日志服务"""

    @staticmethod
    def get_assignment_history(
        task_id=None,
        department_id=None,
        operator_id=None,
        start_date=None,
        end_date=None,
        page=1,
        page_size=20,
    ):
        """
        获取任务分派调整历史记录。

        Returns:
            dict: 包含 results, total, page, page_size, total_pages 的分页结果字典
        """
        # 构建查询条件：筛选包含"调整任务分派"的日志
        query = Q(log_type="status_change", content__contains="调整任务分派")

        if task_id:
            query &= Q(task_id=task_id)

        if department_id:
            # 通过任务查询部门
            query &= Q(task__assigned_department_id=department_id)

        if operator_id:
            # 通过任务或日志操作员查询
            query &= Q(task__assigned_operator_id=operator_id) | Q(
                operator_id=operator_id
            )

        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
                query &= Q(created_at__gte=start_date_obj)
            except ValueError:
                pass

        if end_date:
            try:
                end_date_obj = datetime.strptime(
                    end_date, "%Y-%m-%d"
                ) + timedelta(days=1)
                query &= Q(created_at__lt=end_date_obj)
            except ValueError:
                pass

        # 查询日志
        logs = (
            TaskLog.objects.filter(query)
            .select_related(
                "task",
                "task__assigned_department",
                "task__assigned_operator",
                "operator",
                "task__work_order_process",
                "task__work_order_process__work_order",
            )
            .order_by("-created_at")
        )

        # 分页
        total = logs.count()
        start = (page - 1) * page_size
        end = start + page_size
        logs = logs[start:end]

        # 序列化结果
        serializer = TaskLogSerializer()

        # 构建响应数据，包含额外信息
        results = []
        for log in logs:
            log_data = serializer.to_representation(log)
            # 添加任务和施工单信息
            if log.task:
                log_data["task_info"] = {
                    "id": log.task.id,
                    "work_content": log.task.work_content,
                    "assigned_department": (
                        log.task.assigned_department.name
                        if log.task.assigned_department
                        else None
                    ),
                    "assigned_operator": (
                        log.task.assigned_operator.username
                        if log.task.assigned_operator
                        else None
                    ),
                }
                if (
                    log.task.work_order_process
                    and log.task.work_order_process.work_order
                ):
                    wo = log.task.work_order_process.work_order
                    log_data["work_order_info"] = {
                        "id": wo.id,
                        "order_number": wo.order_number,
                        "customer_name": (
                            wo.customer.name if wo.customer else None
                        ),
                    }
            # 添加操作员名称
            if log.operator:
                log_data["operator_name"] = log.operator.username
            results.append(log_data)

        return {
            "results": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
