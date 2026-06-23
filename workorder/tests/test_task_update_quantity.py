"""
任务报工 update_quantity 接口测试
覆盖工时和设备字段的保存
"""

from decimal import Decimal

import pytest
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient

from workorder.models.core import WorkOrder, WorkOrderProcess, WorkOrderTask
from workorder.models.base import Customer, Process, Department
from workorder.constants.status import TaskStatus


@pytest.fixture
def operator_task(db):
    """创建一个已分派给操作员的任务"""
    customer = Customer.objects.create(
        name="测试客户", contact_person="张", phone="138"
    )
    user = User.objects.create_user(username="task_creator", password="test")
    work_order = WorkOrder.objects.create(
        customer=customer,
        order_number="WO20260607001",
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        production_quantity=100,
        created_by=user,
    )
    process = Process.objects.create(name="印刷", code="PRT")
    wop = WorkOrderProcess.objects.create(
        work_order=work_order, process=process, sequence=10
    )
    dept = Department.objects.create(name="印刷部", code="PRINT")
    operator = User.objects.create_user(
        username="operator", password="test", is_staff=True
    )

    task = WorkOrderTask.objects.create(
        work_order_process=wop,
        task_type="printing",
        status=TaskStatus.PENDING,
        production_quantity=100,
        quantity_completed=0,
    )
    task.assigned_department = dept
    task.assigned_operator = operator
    task.save()

    return task, operator


@pytest.mark.django_db(transaction=True)
class TestTaskUpdateQuantity:
    """测试任务报工 update_quantity 接口"""

    def test_update_quantity_with_work_hours_and_machine(self, operator_task):
        """报工时传入工时和设备信息，结构化字段正确保存"""
        task, operator = operator_task
        client = APIClient()
        client.force_authenticate(user=operator)

        response = client.post(
            f"/api/v1/workorder-tasks/{task.id}/update_quantity/",
            {
                "quantity_increment": 20,
                "quantity_defective": 2,
                "version": task.version,
                "work_hours": 4.5,
                "machine_name": "海德堡CD102",
                "operator_count": 2,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        task.refresh_from_db()
        assert task.quantity_completed == 20
        assert task.work_hours == Decimal("4.5")
        assert task.machine_name == "海德堡CD102"
        assert task.operator_count == 2
        assert task.status == "in_progress"

    def test_update_quantity_without_optional_fields(self, operator_task):
        """报工时不传入工时和设备，结构化字段保持默认值"""
        task, operator = operator_task
        client = APIClient()
        client.force_authenticate(user=operator)

        response = client.post(
            f"/api/v1/workorder-tasks/{task.id}/update_quantity/",
            {
                "quantity_increment": 10,
                "version": task.version,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        task.refresh_from_db()
        assert task.quantity_completed == 10
        assert task.work_hours == Decimal("0")
        assert task.machine_name == ""
        assert task.operator_count == 1
