"""
成本核算服务测试
覆盖施工单完成后自动生成成本核算草稿的场景
"""
from decimal import Decimal

import pytest
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta

from workorder.models.core import WorkOrder, WorkOrderMaterial, WorkOrderTask
from workorder.models.finance import ProductionCost
from workorder.models.materials import Material
from workorder.models.base import Customer, Process
from workorder.models.products import Product
from workorder.models.sales import SalesOrder, SalesOrderItem
from workorder.services.cost_calculation_service import CostCalculationService
from workorder.services.work_order_flow_service import WorkOrderFlowService


@pytest.fixture
def cost_work_order_setup(db):
    """创建一个可完成并触发成本核算的施工单"""
    customer = Customer.objects.create(name="成本测试客户", contact_person="张", phone="138")
    user = User.objects.create_user(username="cost_test_user", password="test")
    product = Product.objects.create(name="成本测试产品", code="COST001", unit="件")

    # 创建物料
    material = Material.objects.create(
        name="灰板纸",
        code="MAT-COST-001",
        unit_price=Decimal("10.00"),
        need_cutting=True,
    )

    sales_order = SalesOrder.objects.create(
        customer=customer,
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        status="approved",
        created_by=user,
    )
    SalesOrderItem.objects.create(
        sales_order=sales_order,
        product=product,
        quantity=100,
        unit="件",
        unit_price=Decimal("100.00"),
    )

    # 创建施工单
    work_order = WorkOrder.objects.create(
        customer=customer,
        sales_order=sales_order,
        order_number="WO20260607COST",
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        production_quantity=100,
        status="in_progress",
        created_by=user,
    )

    # 添加工序和任务
    process = Process.objects.create(
        name="测试工序",
        code="TEST_PROC",
        artwork_required=False,
        die_required=False,
        foiling_plate_required=False,
        embossing_plate_required=False,
    )
    product.default_processes.add(process)

    from workorder.models.core import WorkOrderProcess
    wp = WorkOrderProcess.objects.create(
        work_order=work_order,
        process=process,
        sequence=1,
        status="in_progress",
    )

    # 创建任务
    task = WorkOrderTask.objects.create(
        work_order_process=wp,
        task_type="printing",
        status="in_progress",
        production_quantity=100,
        quantity_completed=0,
    )

    # 添加施工单物料
    wom = WorkOrderMaterial.objects.create(
        work_order=work_order,
        material=material,
        need_cutting=False,
        material_usage="50张",
        actual_unit_price=Decimal("12.50"),
    )

    return work_order, task, wom, material, user


@pytest.mark.django_db(transaction=True)
class TestCostCalculationService:
    """测试成本核算服务"""

    def test_generate_cost_draft_creates_production_cost(self, cost_work_order_setup):
        """施工单完成后应自动生成成本核算草稿"""
        work_order, task, wom, material, user = cost_work_order_setup

        # 确认没有预先存在的成本记录
        assert ProductionCost.objects.filter(work_order=work_order).count() == 0

        # 完成任务
        task.status = "completed"
        task.quantity_completed = 100
        task.work_hours = Decimal("8.00")
        task.operator_count = 2
        task.save()

        # 触发工序完成检查
        task.work_order_process.check_and_update_status()

        # 验证施工单已完成
        work_order.refresh_from_db()
        assert work_order.status == "completed"

        # 验证成本记录已生成
        cost = ProductionCost.objects.filter(work_order=work_order).first()
        assert cost is not None

        # 验证材料成本：50张 * 12.50 = 625.00
        assert cost.material_cost == Decimal("625.00")

        # 验证人工成本：8小时 * 25元/小时 * 2人 = 400.00
        assert cost.labor_cost == Decimal("400.00")

        # 验证总成本
        assert cost.total_cost == Decimal("1025.00")

    def test_generate_cost_draft_idempotent(self, cost_work_order_setup):
        """重复生成成本核算不应创建重复记录"""
        work_order, task, wom, material, user = cost_work_order_setup

        # 直接调用服务两次
        cost1, created1 = CostCalculationService.generate_cost_draft(work_order)
        assert created1 is True

        cost2, created2 = CostCalculationService.generate_cost_draft(work_order)
        assert created2 is False
        assert cost1.id == cost2.id

        # 确保数据库中只有一条记录
        assert ProductionCost.objects.filter(work_order=work_order).count() == 1

    def test_check_and_complete_workorder_triggers_cost(self, cost_work_order_setup):
        """通过 check_and_complete_workorder 也应触发成本核算"""
        work_order, task, wom, material, user = cost_work_order_setup

        # 完成任务
        task.status = "completed"
        task.quantity_completed = 100
        task.work_hours = Decimal("4.00")
        task.operator_count = 1
        task.save()

        # 通过服务标记施工单完成
        result = WorkOrderFlowService.check_and_complete_workorder(work_order=work_order)
        assert result is True

        # 验证成本记录已生成
        work_order.refresh_from_db()
        assert ProductionCost.objects.filter(work_order=work_order).exists()

        cost = ProductionCost.objects.get(work_order=work_order)
        # 材料成本：50 * 12.50 = 625
        assert cost.material_cost == Decimal("625.00")
        # 人工成本：4 * 25 * 1 = 100
        assert cost.labor_cost == Decimal("100.00")
