"""
确认开料接口自动化测试
覆盖状态限制和开料后任务完成
"""
from decimal import Decimal

import pytest
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient

from workorder.models.core import WorkOrder, WorkOrderProcess, WorkOrderTask, WorkOrderMaterial
from workorder.models.materials import Material
from workorder.models.base import Customer, Process
from workorder.constants.status import MaterialPurchaseStatus, TaskStatus, TaskType


@pytest.fixture
def api_client_with_user(db):
    def _make(is_superuser=False):
        user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            email="test@example.com",
            is_staff=True,
            is_superuser=is_superuser,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        return client, user
    return _make


@pytest.fixture
def cutting_work_order(db):
    customer = Customer.objects.create(name="测试客户", contact_person="张", phone="138")
    user = User.objects.create_user(username="cutting_test_user", password="test")
    work_order = WorkOrder.objects.create(
        customer=customer,
        order_number="WO20260607001",
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        production_quantity=100,
        created_by=user,
    )
    return work_order, user


@pytest.fixture
def cutting_material(db, cutting_work_order):
    work_order, user = cutting_work_order
    material = Material.objects.create(name="灰板纸", code="MAT001", need_cutting=True)
    wom = WorkOrderMaterial.objects.create(
        work_order=work_order,
        material=material,
        need_cutting=True,
        material_usage="100张",
        purchase_status=MaterialPurchaseStatus.RECEIVED,
    )
    return wom, work_order, user


@pytest.mark.django_db(transaction=True)
class TestConfirmCutting:
    """测试确认开料接口"""

    def test_pending_status_rejected(self, api_client_with_user, cutting_work_order):
        """pending 状态不能确认开料"""
        client, user = api_client_with_user(is_superuser=True)
        work_order, _ = cutting_work_order
        material = Material.objects.create(name="纸", code="P001", need_cutting=True)
        wom = WorkOrderMaterial.objects.create(
            work_order=work_order,
            material=material,
            need_cutting=True,
            purchase_status=MaterialPurchaseStatus.PENDING,
        )

        response = client.post(f"/api/v1/workorder-materials/{wom.id}/confirm_cutting/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        wom.refresh_from_db()
        assert wom.purchase_status == MaterialPurchaseStatus.PENDING

    def test_ordered_status_rejected(self, api_client_with_user, cutting_work_order):
        """ordered 状态不能确认开料"""
        client, user = api_client_with_user(is_superuser=True)
        work_order, _ = cutting_work_order
        material = Material.objects.create(name="纸", code="P002", need_cutting=True)
        wom = WorkOrderMaterial.objects.create(
            work_order=work_order,
            material=material,
            need_cutting=True,
            purchase_status=MaterialPurchaseStatus.ORDERED,
        )

        response = client.post(f"/api/v1/workorder-materials/{wom.id}/confirm_cutting/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        wom.refresh_from_db()
        assert wom.purchase_status == MaterialPurchaseStatus.ORDERED

    def test_received_status_allowed(self, api_client_with_user, cutting_material):
        """received 状态可以确认开料，结构化字段正确写入"""
        client, user = api_client_with_user(is_superuser=True)
        wom, work_order, _ = cutting_material

        response = client.post(
            f"/api/v1/workorder-materials/{wom.id}/confirm_cutting/",
            {"cut_quantity": 100, "wastage_quantity": 5, "notes": "测试开料"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        wom.refresh_from_db()
        assert wom.purchase_status == MaterialPurchaseStatus.CUT
        assert wom.cut_date is not None
        assert wom.cut_by == user
        assert wom.cut_quantity == Decimal("100")
        assert wom.wastage_quantity == Decimal("5")
        assert "测试开料" in wom.notes
        assert "100" in wom.notes
        assert user.username in wom.notes

    def test_cut_triggers_cutting_task_completion(self, api_client_with_user, cutting_material):
        """确认开料后触发关联开料任务完成"""
        client, user = api_client_with_user(is_superuser=True)
        wom, work_order, _ = cutting_material

        # 创建开料工序和任务
        process = Process.objects.create(name="开料", code="CUT")
        wop = WorkOrderProcess.objects.create(
            work_order=work_order,
            process=process,
            sequence=10,
        )
        task = WorkOrderTask.objects.create(
            work_order_process=wop,
            task_type=TaskType.CUTTING,
            status=TaskStatus.PENDING,
            quantity_completed=0,
            material=wom.material,
            production_quantity=100,
            auto_calculate_quantity=True,
        )

        response = client.post(f"/api/v1/workorder-materials/{wom.id}/confirm_cutting/")
        assert response.status_code == status.HTTP_200_OK

        task.refresh_from_db()
        assert task.status == TaskStatus.COMPLETED

    def test_repeat_cut_rejected(self, api_client_with_user, cutting_material):
        """已开料状态不能重复确认"""
        client, user = api_client_with_user(is_superuser=True)
        wom, work_order, _ = cutting_material
        wom.purchase_status = MaterialPurchaseStatus.CUT
        wom.save()

        response = client.post(f"/api/v1/workorder-materials/{wom.id}/confirm_cutting/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
