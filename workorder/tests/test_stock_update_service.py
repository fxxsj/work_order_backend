"""
StockUpdateService 自动化测试
覆盖包装完成后的批次库存创建/累加逻辑
"""


import pytest
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta

from workorder.models.core import (
    WorkOrder,
    WorkOrderProcess,
    WorkOrderTask,
    WorkOrderProduct,
)
from workorder.models.inventory import ProductStock
from workorder.models.products import Product, ProductStockLog
from workorder.models.base import Customer, Process
from workorder.constants.status import TaskStatus, TaskType
from workorder.services.stock_update_service import StockUpdateService


@pytest.fixture
def customer(db):
    return Customer.objects.create(
        name="测试客户", contact_person="张", phone="138"
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="test")


@pytest.fixture
def work_order(db, customer, user):
    return WorkOrder.objects.create(
        customer=customer,
        order_number="WO20260607001",
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        production_quantity=100,
        created_by=user,
    )


@pytest.fixture
def packaging_process(db, work_order):
    process = Process.objects.create(name="包装", code="PACK")
    return WorkOrderProcess.objects.create(
        work_order=work_order,
        process=process,
        sequence=10,
    )


@pytest.mark.django_db
class TestUpdateProductStockOnPackaging:
    """测试包装完成时的产品库存更新"""

    def test_single_product_packaging_creates_batch(
        self, work_order, packaging_process, user
    ):
        """单产品包装完成后创建 ProductStock 批次"""
        product = Product.objects.create(name="产品A", code="PA001", unit="件")
        WorkOrderProduct.objects.create(
            work_order=work_order, product=product, quantity=50
        )

        _ = WorkOrderTask.objects.create(
            work_order_process=packaging_process,
            task_type=TaskType.PACKAGING,
            status=TaskStatus.COMPLETED,
            product=product,
            quantity_completed=50,
            stock_accounted_quantity=0,
        )

        StockUpdateService.update_product_stock_on_packaging(packaging_process)

        product.refresh_from_db()
        assert product.stock_quantity == 50

        batch = ProductStock.objects.filter(
            batch_no=f"{work_order.order_number}-{product.id}-PKG",
            product=product,
        ).first()
        assert batch is not None
        assert batch.quantity == 50
        assert batch.status == "in_stock"

        # 验证日志
        log = ProductStockLog.objects.filter(product=product).first()
        assert log is not None
        assert log.change_type == "add"
        assert log.quantity == 50

    def test_multi_product_packaging_creates_separate_batches(
        self, work_order, packaging_process, user
    ):
        """多产品包装完成后分别创建批次"""
        product_a = Product.objects.create(
            name="产品A", code="PA001", unit="件"
        )
        product_b = Product.objects.create(
            name="产品B", code="PB001", unit="件"
        )
        WorkOrderProduct.objects.create(
            work_order=work_order, product=product_a, quantity=50
        )
        WorkOrderProduct.objects.create(
            work_order=work_order, product=product_b, quantity=30
        )

        WorkOrderTask.objects.create(
            work_order_process=packaging_process,
            task_type=TaskType.PACKAGING,
            status=TaskStatus.COMPLETED,
            product=product_a,
            quantity_completed=50,
            stock_accounted_quantity=0,
        )
        WorkOrderTask.objects.create(
            work_order_process=packaging_process,
            task_type=TaskType.PACKAGING,
            status=TaskStatus.COMPLETED,
            product=product_b,
            quantity_completed=30,
            stock_accounted_quantity=0,
        )

        StockUpdateService.update_product_stock_on_packaging(packaging_process)

        batch_a = ProductStock.objects.get(product=product_a)
        batch_b = ProductStock.objects.get(product=product_b)

        assert batch_a.quantity == 50
        assert batch_b.quantity == 30
        assert batch_a.batch_no != batch_b.batch_no

    def test_same_product_packaging_again_accumulates_quantity(
        self, work_order, packaging_process, user
    ):
        """同一产品分批包装时，批次数量累加"""
        product = Product.objects.create(name="产品A", code="PA001", unit="件")
        WorkOrderProduct.objects.create(
            work_order=work_order, product=product, quantity=100
        )

        # 第一次包装 40
        _ = WorkOrderTask.objects.create(
            work_order_process=packaging_process,
            task_type=TaskType.PACKAGING,
            status=TaskStatus.COMPLETED,
            product=product,
            quantity_completed=40,
            stock_accounted_quantity=0,
        )
        StockUpdateService.update_product_stock_on_packaging(packaging_process)

        batch = ProductStock.objects.get(product=product)
        assert batch.quantity == 40

        # 第二次包装 60（新任务）
        _ = WorkOrderTask.objects.create(
            work_order_process=packaging_process,
            task_type=TaskType.PACKAGING,
            status=TaskStatus.COMPLETED,
            product=product,
            quantity_completed=60,
            stock_accounted_quantity=0,
        )
        StockUpdateService.update_product_stock_on_packaging(packaging_process)

        batch.refresh_from_db()
        assert batch.quantity == 100

    def test_repeated_call_is_idempotent(
        self, work_order, packaging_process, user
    ):
        """重复调用 update_product_stock_on_packaging 不会重复增加库存"""
        product = Product.objects.create(name="产品A", code="PA001", unit="件")
        WorkOrderProduct.objects.create(
            work_order=work_order, product=product, quantity=50
        )

        _ = WorkOrderTask.objects.create(
            work_order_process=packaging_process,
            task_type=TaskType.PACKAGING,
            status=TaskStatus.COMPLETED,
            product=product,
            quantity_completed=50,
            stock_accounted_quantity=0,
        )

        # 第一次调用
        StockUpdateService.update_product_stock_on_packaging(packaging_process)
        product.refresh_from_db()
        assert product.stock_quantity == 50
        batch = ProductStock.objects.get(product=product)
        assert batch.quantity == 50

        # 重复调用
        StockUpdateService.update_product_stock_on_packaging(packaging_process)
        product.refresh_from_db()
        assert product.stock_quantity == 50
        batch.refresh_from_db()
        assert batch.quantity == 50

        # 验证日志只创建了一条（第一次的）
        logs = ProductStockLog.objects.filter(product=product)
        assert logs.count() == 1
