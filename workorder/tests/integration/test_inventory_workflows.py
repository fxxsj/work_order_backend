"""Integration tests for inventory workflows"""
import pytest
from django.utils import timezone
from rest_framework import status

from workorder.models import ProductStock, StockIn
from workorder.tests.factories import UserFactory, WorkOrderFactory, WorkOrderProductFactory


@pytest.mark.django_db
@pytest.mark.integration
class TestInventoryWorkflow:
    def test_stock_in_approve_creates_product_stock(self, api_client):
        """
        GIVEN: A submitted stock-in record
        WHEN: Approve the stock-in
        THEN: ProductStock records are created for work order products
        """
        user = UserFactory(is_superuser=True)
        work_order = WorkOrderFactory(processes=0)
        product_line = WorkOrderProductFactory(work_order=work_order, quantity=100)

        stock_in = StockIn.objects.create(
            work_order=work_order,
            stock_in_date=timezone.now().date(),
            status="submitted",
            submitted_by=user,
            submitted_at=timezone.now(),
        )

        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/v1/stock-ins/{stock_in.id}/approve/", format="json")

        assert response.status_code == status.HTTP_200_OK
        stock_in.refresh_from_db()
        assert stock_in.status == "completed"

        expected_batch = f"{stock_in.order_number}-{product_line.id}"
        assert ProductStock.objects.filter(
            batch_no=expected_batch,
            product=product_line.product,
            work_order=work_order,
        ).exists()
