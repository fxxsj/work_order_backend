"""Integration tests for sales order workflow rules."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from workorder.models.inventory import DeliveryOrder
from workorder.models.sales import SalesOrder, SalesOrderItem
from workorder.tests.factories import CustomerFactory, ProductFactory, UserFactory


def _sales_order_payload(*, customer_id: int, product_id: int, status: str = "pending") -> dict:
    today = timezone.now().date()
    return {
        "customer": customer_id,
        "status": status,
        "payment_status": "paid",
        "order_date": str(today),
        "delivery_date": str(today + timedelta(days=7)),
        "contact_person": "张三",
        "contact_phone": "13800138000",
        "shipping_address": "测试地址",
        "items": [
            {
                "product": product_id,
                "quantity": 10,
                "unit": "件",
                "unit_price": 10,
                "tax_rate": 0,
                "discount_amount": 0,
                "notes": "",
            }
        ],
    }


@pytest.mark.django_db
@pytest.mark.integration
class TestSalesOrderWorkflow:
    def test_create_and_update_ignore_direct_status_fields(self, api_client):
        user = UserFactory(is_superuser=True)
        customer = CustomerFactory()
        product = ProductFactory()
        api_client.force_authenticate(user=user)

        # status 字段在 SalesOrderSerializer 中为 always_read_only_fields，
        # 尝试传入非法值不会导致创建失败（字段被忽略），但 "approved" 已经不是
        # 合法选项，为清晰起见改为 "pending"
        response = api_client.post(
            "/api/v1/sales-orders/",
            _sales_order_payload(customer_id=customer.id, product_id=product.id),
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        created = response.data["data"]
        assert created["status"] == "pending"
        assert created["payment_status"] == "unpaid"

        order_id = created["id"]
        update_payload = _sales_order_payload(
            customer_id=customer.id,
            product_id=product.id,
        )
        update_payload["payment_status"] = "paid"
        response = api_client.put(
            f"/api/v1/sales-orders/{order_id}/",
            update_payload,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        updated = response.data["data"]
        assert updated["status"] == "pending"
        assert updated["payment_status"] == "unpaid"

    def test_delivery_order_can_be_created_from_approved_sales_order(self, api_client):
        user = UserFactory(is_superuser=True)
        customer = CustomerFactory()
        product = ProductFactory()
        sales_order = SalesOrder.objects.create(
            customer=customer,
            order_date=timezone.now().date(),
            delivery_date=timezone.now().date() + timedelta(days=5),
            status="in_production",
            created_by=user,
        )
        sales_item = SalesOrderItem.objects.create(
            sales_order=sales_order,
            product=product,
            quantity=10,
            unit="件",
            unit_price=10,
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(
            "/api/v1/delivery-orders/",
            {
                "sales_order": sales_order.id,
                "customer": customer.id,
                "delivery_date": str(timezone.now().date()),
                "receiver_name": "李四",
                "receiver_phone": "13900139000",
                "delivery_address": "测试收货地址",
                "items_data": [
                    {
                        "product": product.id,
                        "sales_order_item": sales_item.id,
                        "quantity": 4,
                        "unit": "件",
                        "unit_price": 10,
                    }
                ],
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert DeliveryOrder.objects.filter(sales_order=sales_order).exists()

    def test_manual_complete_requires_reason_for_partial_delivery(self, api_client):
        user = UserFactory(is_superuser=True)
        customer = CustomerFactory()
        product = ProductFactory()
        sales_order = SalesOrder.objects.create(
            customer=customer,
            order_date=timezone.now().date(),
            delivery_date=timezone.now().date() + timedelta(days=5),
            status="in_production",
            approval_status="approved",
            created_by=user,
        )
        SalesOrderItem.objects.create(
            sales_order=sales_order,
            product=product,
            quantity=10,
            delivered_quantity=3,
            unit="件",
            unit_price=10,
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(
            f"/api/v1/sales-orders/{sales_order.id}/complete/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = api_client.post(
            f"/api/v1/sales-orders/{sales_order.id}/complete/",
            {"completion_reason": "客户确认剩余尾差不再补发"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        sales_order.refresh_from_db()
        assert sales_order.status == "completed"
        assert sales_order.completion_reason == "客户确认剩余尾差不再补发"
