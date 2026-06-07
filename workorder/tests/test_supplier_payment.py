"""
供应商付款模型与应付账款测试
覆盖付款创建、审核、回写采购单付款状态
"""
from decimal import Decimal

import pytest
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta

from workorder.models.finance import SupplierPayment
from workorder.models.materials import PurchaseOrder, PurchaseOrderItem, Supplier, Material
from workorder.services.supplier_payment_service import SupplierPaymentService


@pytest.fixture
def purchase_setup(db):
    """创建采购单和供应商"""
    user = User.objects.create_user(username="po_test_user", password="test", is_staff=True, is_superuser=True)
    supplier = Supplier.objects.create(name="测试供应商", code="SUP001")
    material = Material.objects.create(name="灰板纸", code="MAT001", unit_price=Decimal("10.00"))

    po = PurchaseOrder.objects.create(
        supplier=supplier,
        order_number="PO20260607001",
        status="received",
        total_amount=Decimal("1000.00"),
    )
    PurchaseOrderItem.objects.create(
        purchase_order=po,
        material=material,
        quantity=Decimal("100"),
        unit_price=Decimal("10.00"),
    )
    return po, supplier, user


@pytest.mark.django_db(transaction=True)
class TestSupplierPayment:
    """测试供应商付款"""

    def test_create_supplier_payment(self, purchase_setup):
        """创建供应商付款记录"""
        po, supplier, user = purchase_setup
        payment = SupplierPayment.objects.create(
            purchase_order=po,
            supplier=supplier,
            amount=Decimal("500.00"),
            applied_amount=Decimal("500.00"),
            payment_method="transfer",
            created_by=user,
        )
        assert payment.payment_number.startswith("FK")
        assert payment.remaining_amount == Decimal("0")
        assert payment.status == "pending"

    def test_payment_approve_updates_purchase_order(self, purchase_setup):
        """付款审核通过后回写采购单付款状态"""
        po, supplier, user = purchase_setup
        payment = SupplierPayment.objects.create(
            purchase_order=po,
            supplier=supplier,
            amount=Decimal("500.00"),
            applied_amount=Decimal("500.00"),
            payment_method="transfer",
            created_by=user,
        )
        # 模拟审核通过
        payment.status = "approved"
        payment.save()

        # 调用服务回写
        SupplierPaymentService.apply_payment(payment=payment)

        po.refresh_from_db()
        assert po.paid_amount == Decimal("500.00")
        assert po.payment_status == "partial"

    def test_full_payment_updates_status_to_paid(self, purchase_setup):
        """全额付款后采购单状态变为已付款"""
        po, supplier, user = purchase_setup
        payment = SupplierPayment.objects.create(
            purchase_order=po,
            supplier=supplier,
            amount=Decimal("1000.00"),
            applied_amount=Decimal("1000.00"),
            payment_method="transfer",
            created_by=user,
        )
        payment.status = "approved"
        payment.save()

        SupplierPaymentService.apply_payment(payment=payment)

        po.refresh_from_db()
        assert po.paid_amount == Decimal("1000.00")
        assert po.payment_status == "paid"

    def test_multiple_payments_aggregate(self, purchase_setup):
        """多笔付款金额应汇总"""
        po, supplier, user = purchase_setup
        for amt in [Decimal("300.00"), Decimal("200.00")]:
            p = SupplierPayment.objects.create(
                purchase_order=po,
                supplier=supplier,
                amount=amt,
                applied_amount=amt,
                payment_method="transfer",
                created_by=user,
            )
            p.status = "approved"
            p.save()
            SupplierPaymentService.apply_payment(payment=p)

        po.refresh_from_db()
        assert po.paid_amount == Decimal("500.00")
        assert po.payment_status == "partial"
