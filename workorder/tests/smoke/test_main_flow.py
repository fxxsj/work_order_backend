"""
主流程冒烟测试

覆盖 MVP 核心链路：
客户/产品/客户订单 → 生成施工单 → 提交审核 → 审核通过 → 自动生成任务 →
操作员完成任务 → 施工单自动完工
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from workorder.constants.status import (
    SalesOrderStatus,
    TaskStatus,
    WorkOrderApprovalStatus,
    WorkOrderStatus,
)
from workorder.models.base import Customer, Process
from workorder.models.core import WorkOrderTask
from workorder.models.products import Product
from workorder.models.sales import SalesOrder, SalesOrderItem
from workorder.services.service_errors import ServiceError
from workorder.services.work_order_flow_service import WorkOrderFlowService


class MainFlowSmokeTest(TestCase):
    """MVP 主流程端到端冒烟测试"""

    def setUp(self):
        self.salesperson = User.objects.create_user(
            username="smoke_sales", password="123456"
        )
        self.approver = User.objects.create_user(
            username="smoke_approver", password="123456"
        )
        self.approver.is_superuser = True
        self.approver.is_staff = True
        self.approver.save(update_fields=["is_superuser", "is_staff"])
        self.operator = User.objects.create_user(
            username="smoke_operator", password="123456"
        )

        self.customer = Customer.objects.create(
            name="冒烟客户",
            contact_person="李四",
            phone="13800138000",
            salesperson=self.salesperson,
        )

        self.product = Product.objects.create(
            name="冒烟产品",
            code="SMOKE001",
            unit_price=10.0,
        )
        self.process = Process.objects.create(
            name="冒烟工序",
            code="SMOKE_PROC",
            artwork_required=False,
            die_required=False,
            foiling_plate_required=False,
            embossing_plate_required=False,
        )
        self.product.default_processes.add(self.process)

        self.sales_order = SalesOrder.objects.create(
            order_number="SO20260623001",
            customer=self.customer,
            order_date=timezone.now().date(),
            delivery_date=timezone.now().date() + timedelta(days=7),
            total_amount=1000.0,
            status=SalesOrderStatus.APPROVED,
            created_by=self.salesperson,
        )
        SalesOrderItem.objects.create(
            sales_order=self.sales_order,
            product=self.product,
            quantity=100,
            unit_price=10.0,
        )

    def test_main_flow_sales_order_to_work_order_completion(self):
        """主流程：客户订单 → 施工单 → 任务 → 完工"""
        # 1. 从客户订单生成施工单
        work_order = WorkOrderFlowService.create_from_sales_order(
            sales_order_id=self.sales_order.id,
            production_quantity=100,
            delivery_date=timezone.now().date() + timedelta(days=7),
            priority="normal",
            notes="冒烟测试",
            created_by=self.salesperson,
        )
        self.assertEqual(work_order.status, WorkOrderStatus.PENDING)
        self.assertEqual(
            work_order.approval_status, WorkOrderApprovalStatus.DRAFT
        )

        # 2. 提交审核
        work_order = WorkOrderFlowService.submit_for_approval(
            work_order_id=work_order.id,
            submitted_by=self.salesperson,
        )
        self.assertEqual(
            work_order.approval_status, WorkOrderApprovalStatus.SUBMITTED
        )

        # 3. 审核通过（应自动生成任务并把施工单置为生产中）
        work_order = WorkOrderFlowService.handle_approval_passed(
            work_order=work_order,
            approved_by=self.approver,
            comment="审核通过",
        )
        self.assertEqual(
            work_order.approval_status, WorkOrderApprovalStatus.APPROVED
        )
        self.assertEqual(work_order.status, WorkOrderStatus.IN_PROGRESS)

        tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order
        )
        self.assertGreater(tasks.count(), 0)

        # 4. 操作员完成所有任务
        tasks.update(status=TaskStatus.COMPLETED)

        # 5. 施工单自动完工
        is_completed = WorkOrderFlowService.check_and_complete_workorder(
            work_order=work_order
        )
        self.assertTrue(is_completed)
        work_order.refresh_from_db()
        self.assertEqual(work_order.status, WorkOrderStatus.COMPLETED)

    def test_invalid_work_order_transition_raises_service_error(self):
        """非法状态转换应抛出 ServiceError"""
        work_order = WorkOrderFlowService.create_from_sales_order(
            sales_order_id=self.sales_order.id,
            production_quantity=100,
            delivery_date=timezone.now().date() + timedelta(days=7),
            created_by=self.salesperson,
        )

        # 未提交就审核应失败
        with self.assertRaises(ServiceError):
            WorkOrderFlowService.handle_approval_passed(
                work_order=work_order,
                approved_by=self.approver,
                comment="非法审核",
            )
