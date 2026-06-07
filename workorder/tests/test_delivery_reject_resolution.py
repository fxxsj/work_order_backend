"""
送货单拒收后处理动作测试
覆盖补发、返工、终止三种动作
"""
from decimal import Decimal

import pytest
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient

from workorder.models.core import WorkOrder, WorkOrderProduct
from workorder.models.inventory import DeliveryOrder, DeliveryItem, ProductStock
from workorder.models.sales import SalesOrder, SalesOrderItem
from workorder.models.products import Product
from workorder.models.base import Customer


@pytest.fixture
def rejected_delivery(db):
    """创建一个已拒收的送货单"""
    customer = Customer.objects.create(name="测试客户", contact_person="张", phone="138")
    user = User.objects.create_user(username="reject_test_user", password="test", is_staff=True, is_superuser=True)
    product = Product.objects.create(name="产品A", code="PA001", unit="件")

    sales_order = SalesOrder.objects.create(
        customer=customer,
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date(),
        status="in_production",
        created_by=user,
    )
    SalesOrderItem.objects.create(
        sales_order=sales_order,
        product=product,
        quantity=50,
        unit="件",
        unit_price=100,
    )

    delivery = DeliveryOrder.objects.create(
        sales_order=sales_order,
        customer=customer,
        status="rejected",
        receiver_name="李四",
        receiver_phone="13900139000",
        delivery_address="测试地址",
    )
    DeliveryItem.objects.create(
        delivery_order=delivery,
        product=product,
        sales_order_item=sales_order.items.first(),
        quantity=Decimal("50"),
        unit="件",
        unit_price=Decimal("100"),
    )
    # 创建库存用于拒收回退
    ProductStock.objects.create(
        product=product,
        quantity=0,
        batch_no="REJECT-TEST",
        status="in_stock",
        quality_status="qualified",
    )

    return delivery, user, product, sales_order


@pytest.mark.django_db(transaction=True)
class TestDeliveryRejectResolution:
    """测试拒收处理动作"""

    def test_reship_creates_new_delivery_order(self, rejected_delivery):
        """补发时自动生成新的送货单"""
        delivery, user, product, sales_order = rejected_delivery
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            f"/api/v1/delivery-orders/{delivery.id}/resolve_exception/",
            {"resolution": "reship", "resolution_notes": "客户要求补发"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert "reship_order_id" in data
        assert "reship_order_number" in data

        # 验证新送货单
        new_delivery = DeliveryOrder.objects.get(id=data["reship_order_id"])
        assert new_delivery.status == "pending"
        assert new_delivery.items.count() == 1
        assert new_delivery.items.first().quantity == Decimal("50")

    def test_rework_creates_rework_work_order(self, rejected_delivery):
        """返工时自动生成返工施工单"""
        delivery, user, product, sales_order = rejected_delivery
        # 先给销售订单关联产品，确保能生成施工单
        sales_order.items.first().product = product
        sales_order.items.first().save()

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            f"/api/v1/delivery-orders/{delivery.id}/resolve_exception/",
            {"resolution": "rework", "resolution_notes": "产品不合格需返工"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert "rework_work_order_id" in data

        # 验证返工施工单
        rework = WorkOrder.objects.get(id=data["rework_work_order_id"])
        assert rework.sales_order == sales_order
        assert "返工" in rework.notes

    def test_terminate_cancels_sales_order(self, rejected_delivery):
        """终止时取消客户订单"""
        delivery, user, product, sales_order = rejected_delivery
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            f"/api/v1/delivery-orders/{delivery.id}/resolve_exception/",
            {"resolution": "terminate", "resolution_notes": "客户终止订单"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["sales_order_status"] == "cancelled"

        sales_order.refresh_from_db()
        assert sales_order.status == "cancelled"

    def test_invalid_resolution_rejected(self, rejected_delivery):
        """无效的处理结论被拒绝"""
        delivery, user, product, sales_order = rejected_delivery
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            f"/api/v1/delivery-orders/{delivery.id}/resolve_exception/",
            {"resolution": "unknown", "resolution_notes": "测试"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST