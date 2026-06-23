"""
TaskActionService 测试用例

测试任务操作服务的状态流转、分派、取消和拆分。
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from workorder.models.base import Customer, Department, Process
from workorder.models.core import (
    WorkOrder,
    WorkOrderProcess,
    WorkOrderTask,
)
from workorder.constants.status import TaskStatus
from workorder.services.service_errors import ServiceError
from workorder.services.task_action_service import TaskActionService


@pytest.fixture
def task_setup(db):
    """创建任务测试数据。"""
    customer = Customer.objects.create(
        name="测试客户", contact_person="张", phone="138"
    )
    creator = User.objects.create_user(
        username="task_creator", password="test"
    )
    operator = User.objects.create_user(
        username="operator", password="test", is_staff=True
    )
    supervisor = User.objects.create_user(
        username="supervisor", password="test", is_staff=True
    )

    work_order = WorkOrder.objects.create(
        customer=customer,
        order_number="WO20260607001",
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        production_quantity=100,
        created_by=creator,
    )
    process = Process.objects.create(name="印刷", code="PRT")
    wop = WorkOrderProcess.objects.create(
        work_order=work_order, process=process, sequence=10
    )
    dept = Department.objects.create(name="印刷部", code="PRINT")
    dept.processes.add(process)

    task = WorkOrderTask.objects.create(
        work_order_process=wop,
        task_type="printing",
        status=TaskStatus.PENDING,
        production_quantity=100,
        quantity_completed=0,
        assigned_department=dept,
        assigned_operator=operator,
    )

    return {
        "task": task,
        "operator": operator,
        "supervisor": supervisor,
        "department": dept,
        "work_order": work_order,
    }


@pytest.mark.django_db
class TestTaskActionService:
    """任务操作服务测试"""

    def test_update_quantity_increments_and_sets_in_progress(self, task_setup):
        """测试更新数量后任务变为进行中"""
        task = task_setup["task"]

        result = TaskActionService.update_quantity(
            task=task,
            quantity_increment=20,
            quantity_defective=2,
            notes="测试报工",
            user=task_setup["operator"],
        )

        assert result.quantity_completed == 20
        assert result.quantity_defective == 2
        assert result.status == TaskStatus.IN_PROGRESS
        assert result.production_requirements == "测试报工"

    def test_update_quantity_completes_task(self, task_setup):
        """测试更新数量达到生产数量后任务完成"""
        task = task_setup["task"]

        result = TaskActionService.update_quantity(
            task=task,
            quantity_increment=100,
            user=task_setup["operator"],
        )

        assert result.status == TaskStatus.COMPLETED
        assert result.quantity_completed == 100

    def test_update_quantity_missing_increment(self, task_setup):
        """测试缺少增量数量时抛出错误"""
        task = task_setup["task"]

        with pytest.raises(ServiceError) as exc_info:
            TaskActionService.update_quantity(
                task=task,
                quantity_increment=None,
                user=task_setup["operator"],
            )

        assert exc_info.value.code == 400

    def test_complete_task_sets_full_quantity(self, task_setup):
        """测试强制完成任务设置完成数量为生产数量"""
        task = task_setup["task"]

        result = TaskActionService.complete_task(
            task=task,
            completion_reason="客户催单",
            user=task_setup["operator"],
        )

        assert result.status == TaskStatus.COMPLETED
        assert result.quantity_completed == 100

    def test_cancel_task_success(self, task_setup):
        """测试取消任务成功"""
        task = task_setup["task"]

        result = TaskActionService.cancel_task(
            task=task,
            cancellation_reason="物料未到",
            user=task_setup["operator"],
        )

        assert result.status == TaskStatus.CANCELLED
        assert result.version == 2

    def test_cancel_already_cancelled_task_fails(self, task_setup):
        """测试重复取消任务失败"""
        task = task_setup["task"]
        task.status = TaskStatus.CANCELLED
        task.save()

        with pytest.raises(ServiceError) as exc_info:
            TaskActionService.cancel_task(
                task=task,
                cancellation_reason="重复取消",
                user=task_setup["operator"],
            )

        assert exc_info.value.code == 400

    def test_split_task_success(self, task_setup):
        """测试拆分任务成功"""
        task = task_setup["task"]

        result = TaskActionService.split_task(
            task=task,
            splits=[
                {"production_quantity": 40},
                {"production_quantity": 60},
            ],
            user=task_setup["operator"],
        )

        assert len(result["created_subtasks"]) == 2
        assert result["total_split_quantity"] == 100
        assert task.status == TaskStatus.IN_PROGRESS

    def test_split_task_quantity_exceeds_parent(self, task_setup):
        """测试子任务数量超过父任务时失败"""
        task = task_setup["task"]

        with pytest.raises(ServiceError) as exc_info:
            TaskActionService.split_task(
                task=task,
                splits=[
                    {"production_quantity": 60},
                    {"production_quantity": 60},
                ],
                user=task_setup["operator"],
            )

        assert exc_info.value.code == 400
