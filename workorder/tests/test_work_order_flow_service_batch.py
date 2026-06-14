"""
WorkOrderFlowService 批量创建测试用例
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from workorder.models.base import Customer, Process
from workorder.models.core import WorkOrder
from workorder.models.products import Product
from workorder.models.sales import SalesOrder, SalesOrderItem
from workorder.services.service_errors import ServiceError
from workorder.services.work_order_flow_service import WorkOrderFlowService


@pytest.fixture
def batch_setup(db):
    """创建批量创建施工单测试数据。"""
    customer = Customer.objects.create(name="测试客户", contact_person="张", phone="138")
    user = User.objects.create_user(username="batch_creator", password="test")
    product = Product.objects.create(name="测试产品", code="TEST001", unit="件")
    process = Process.objects.create(name="测试工序", code="TEST_PROC")
    product.default_processes.add(process)

    sales_orders = []
    for i in range(3):
        so = SalesOrder.objects.create(
            customer=customer,
            order_number=f"SO2026060300{i+1}",
            order_date=timezone.now().date(),
            delivery_date=timezone.now().date() + timedelta(days=7),
            total_amount=1000.0,
            status="approved",
            created_by=user,
        )
        SalesOrderItem.objects.create(
            sales_order=so,
            product=product,
            quantity=100,
            unit_price=10.0,
        )
        sales_orders.append(so)

    return {
        "sales_orders": sales_orders,
        "user": user,
    }


@pytest.mark.django_db
class TestWorkOrderFlowServiceBatch:
    """WorkOrderFlowService 批量创建测试"""

    def test_create_from_sales_orders_batch_success(self, batch_setup):
        """测试批量创建施工单成功"""
        sales_orders = batch_setup["sales_orders"]
        user = batch_setup["user"]

        result = WorkOrderFlowService.create_from_sales_orders_batch(
            sales_order_ids=[so.id for so in sales_orders],
            request_data={
                "production_quantity": 100,
                "delivery_date": timezone.now().date() + timedelta(days=7),
                "priority": "normal",
                "notes": "",
            },
            user=user,
        )

        assert len(result["created"]) == 3
        assert len(result["failed"]) == 0
        assert WorkOrder.objects.count() == 3

    def test_create_from_sales_orders_batch_empty_list(self, batch_setup):
        """测试空列表失败"""
        user = batch_setup["user"]

        with pytest.raises(ServiceError) as exc_info:
            WorkOrderFlowService.create_from_sales_orders_batch(
                sales_order_ids=[],
                request_data={},
                user=user,
            )

        assert exc_info.value.code == 400
