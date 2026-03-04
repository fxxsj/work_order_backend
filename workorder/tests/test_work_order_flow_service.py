"""
WorkOrderFlowService 测试用例

测试施工单流程编排服务的各个场景
"""

from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from workorder.models.core import WorkOrder, WorkOrderTask
from workorder.models.sales import SalesOrder, SalesOrderItem
from workorder.models.base import Customer, Process
from workorder.models.products import Product
from workorder.services.work_order_flow_service import WorkOrderFlowService
from workorder.services.service_errors import ServiceError


class WorkOrderFlowServiceTest(TestCase):
    """施工单流程编排服务测试"""

    def setUp(self):
        """测试数据准备"""
        # 创建用户
        self.salesperson = User.objects.create_user(
            username="salesperson", password="123456"
        )
        self.creator = User.objects.create_user(
            username="creator", password="123456"
        )
        self.approver = User.objects.create_user(
            username="approver", password="123456"
        )
        self.operator = User.objects.create_user(
            username="operator", password="123456"
        )

        # 创建客户
        self.customer = Customer.objects.create(
            name="测试客户",
            contact_person="张三",
            phone="13800138000",
            salesperson=self.salesperson,
        )

        # 创建产品
        self.product = Product.objects.create(
            name="测试产品",
            code="TEST001",
            unit_price=10.0,
        )
        self.process = Process.objects.create(
            name="测试工序",
            code="TEST_PROC",
            artwork_required=False,
            die_required=False,
            foiling_plate_required=False,
            embossing_plate_required=False,
        )
        self.product.default_processes.add(self.process)

        # 创建销售订单
        self.sales_order = SalesOrder.objects.create(
            order_number="SO20260303001",
            customer=self.customer,
            order_date=timezone.now().date(),
            delivery_date=timezone.now().date() + timedelta(days=7),
            total_amount=1000.0,
            status="confirmed",
            created_by=self.salesperson,
        )

        # 添加销售订单明细
        SalesOrderItem.objects.create(
            sales_order=self.sales_order,
            product=self.product,
            quantity=100,
            unit_price=10.0,
        )

    # ========== 测试流程 1: 从销售订单创建施工单 ==========

    def test_create_from_sales_order_success(self):
        """测试成功从销售订单创建施工单"""
        work_order = WorkOrderFlowService.create_from_sales_order(
            sales_order_id=self.sales_order.id,
            production_quantity=100,
            delivery_date=timezone.now().date() + timedelta(days=7),
            priority="normal",
            notes="测试备注",
            created_by=self.creator,
        )

        # 验证施工单创建成功
        self.assertIsNotNone(work_order)
        self.assertEqual(work_order.customer, self.customer)
        self.assertEqual(work_order.production_quantity, 100)
        self.assertEqual(work_order.status, "pending")
        self.assertEqual(work_order.approval_status, "pending")

        # 验证施工单号格式
        self.assertTrue(work_order.order_number.startswith("WO"))
        self.assertTrue(work_order.order_number.endswith("001"))

    def test_create_from_sales_order_invalid_status(self):
        """测试销售订单状态不正确时创建失败"""
        # 修改销售订单状态
        self.sales_order.status = "cancelled"
        self.sales_order.save()

        # 应该抛出错误
        with self.assertRaises(ServiceError) as context:
            WorkOrderFlowService.create_from_sales_order(
                sales_order_id=self.sales_order.id,
                production_quantity=100,
                created_by=self.creator,
            )

        self.assertIn("只有已确认的销售订单才能创建施工单", str(context.exception))

    def test_create_from_sales_order_not_found(self):
        """测试销售订单不存在时创建失败"""
        with self.assertRaises(ServiceError) as context:
            WorkOrderFlowService.create_from_sales_order(
                sales_order_id=99999,  # 不存在的ID
                production_quantity=100,
                created_by=self.creator,
            )

        self.assertIn("销售订单不存在", str(context.exception))

    # ========== 测试流程 2: 提交审核 ==========

    def test_submit_for_approval_success(self):
        """测试成功提交审核"""
        # 先创建施工单
        work_order = WorkOrderFlowService.create_from_sales_order(
            sales_order_id=self.sales_order.id,
            production_quantity=100,
            created_by=self.creator,
        )

        # 提交审核
        updated_work_order = WorkOrderFlowService.submit_for_approval(
            work_order_id=work_order.id,
            submitted_by=self.creator,
            comment="请审核",
        )

        # 验证状态变更
        self.assertEqual(updated_work_order.approval_status, "pending")

    def test_submit_for_approval_invalid_transition(self):
        """测试无效的状态转换"""
        # 先创建施工单
        work_order = WorkOrderFlowService.create_from_sales_order(
            sales_order_id=self.sales_order.id,
            production_quantity=100,
            created_by=self.creator,
        )

        # 修改状态为已审核
        work_order.approval_status = "approved"
        work_order.save()

        # 再次提交审核应该失败
        with self.assertRaises(ServiceError) as context:
            WorkOrderFlowService.submit_for_approval(
                work_order_id=work_order.id,
                submitted_by=self.creator,
            )

        self.assertIn("不允许的状态转换", str(context.exception))

    # ========== 测试流程 3: 审核通过 ==========

    def test_handle_approval_passed_success(self):
        """测试审核通过成功"""
        # 创建并提交审核
        work_order = WorkOrderFlowService.create_from_sales_order(
            sales_order_id=self.sales_order.id,
            production_quantity=100,
            created_by=self.creator,
        )
        WorkOrderFlowService.submit_for_approval(
            work_order_id=work_order.id,
            submitted_by=self.creator,
        )

        # 审核通过
        updated_work_order = WorkOrderFlowService.handle_approval_passed(
            work_order=work_order,
            approved_by=self.approver,
            comment="审核通过",
        )

        # 验证状态
        self.assertEqual(updated_work_order.approval_status, "approved")
        self.assertEqual(updated_work_order.status, "in_progress")
        self.assertEqual(updated_work_order.approved_by, self.approver)
        self.assertIsNotNone(updated_work_order.approved_at)

    # ========== 测试流程 4: 审核拒绝 ==========

    def test_handle_approval_rejected_success(self):
        """测试审核拒绝成功"""
        # 创建并提交审核
        work_order = WorkOrderFlowService.create_from_sales_order(
            sales_order_id=self.sales_order.id,
            production_quantity=100,
            created_by=self.creator,
        )
        WorkOrderFlowService.submit_for_approval(
            work_order_id=work_order.id,
            submitted_by=self.creator,
        )

        # 审核拒绝
        updated_work_order = WorkOrderFlowService.handle_approval_rejected(
            work_order=work_order,
            rejected_by=self.approver,
            reason="数据不完整",
        )

        # 验证状态
        self.assertEqual(updated_work_order.approval_status, "rejected")
        self.assertEqual(updated_work_order.approved_by, self.approver)
        self.assertEqual(updated_work_order.approval_comment, "数据不完整")

        # 验证草稿任务已删除
        draft_tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order,
            status="draft",
        )
        self.assertEqual(draft_tasks.count(), 0)

    # ========== 测试流程 5: 检查并完成施工单 ==========

    def test_check_and_complete_workorder_success(self):
        """测试所有任务完成后自动标记施工单为完成"""
        # 创建、提交审核、审核通过
        work_order = WorkOrderFlowService.create_from_sales_order(
            sales_order_id=self.sales_order.id,
            production_quantity=100,
            created_by=self.creator,
        )
        WorkOrderFlowService.submit_for_approval(
            work_order_id=work_order.id,
            submitted_by=self.creator,
        )
        WorkOrderFlowService.handle_approval_passed(
            work_order=work_order,
            approved_by=self.approver,
        )

        # 完成所有任务
        WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order
        ).update(status="completed")

        # 检查并完成
        is_completed = WorkOrderFlowService.check_and_complete_workorder(
            work_order=work_order
        )

        # 验证
        self.assertTrue(is_completed)
        work_order.refresh_from_db()
        self.assertEqual(work_order.status, "completed")

    def test_check_and_complete_workorder_incomplete(self):
        """测试任务未完成时不标记施工单为完成"""
        # 创建并审核通过
        work_order = WorkOrderFlowService.create_from_sales_order(
            sales_order_id=self.sales_order.id,
            production_quantity=100,
            created_by=self.creator,
        )
        WorkOrderFlowService.submit_for_approval(
            work_order_id=work_order.id,
            submitted_by=self.creator,
        )
        WorkOrderFlowService.handle_approval_passed(
            work_order=work_order,
            approved_by=self.approver,
        )

        # 只完成部分任务
        tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order
        )
        if tasks.exists():
            tasks.first().status = "completed"
            tasks.first().save()

        # 检查并完成
        is_completed = WorkOrderFlowService.check_and_complete_workorder(
            work_order=work_order
        )

        # 验证
        self.assertFalse(is_completed)
        work_order.refresh_from_db()
        self.assertEqual(work_order.status, "in_progress")

    # ========== 测试状态转换验证 ==========

    def test_validate_status_transition_valid(self):
        """测试有效的状态转换"""
        # 不应该抛出异常
        WorkOrderFlowService._validate_status_transition("pending", "pending")
        WorkOrderFlowService._validate_status_transition("pending", "approved")
        WorkOrderFlowService._validate_status_transition("rejected", "pending")

    def test_validate_status_transition_invalid(self):
        """测试无效的状态转换"""
        with self.assertRaises(ServiceError):
            WorkOrderFlowService._validate_status_transition("completed", "in_progress")

        with self.assertRaises(ServiceError):
            WorkOrderFlowService._validate_status_transition("approved", "pending")


# ========== 集成测试：完整流程 ==========

class WorkOrderFlowIntegrationTest(TestCase):
    """施工单流程集成测试"""

    def setUp(self):
        """测试数据准备"""
        self.user = User.objects.create_user(
            username="testuser", password="123456"
        )
        self.customer = Customer.objects.create(
            name="集成测试客户",
            contact_person="李四",
            phone="13900139000",
            salesperson=self.user,
        )
        self.product = Product.objects.create(
            name="集成测试产品",
            code="INT001",
            unit_price=50.0,
        )
        self.process = Process.objects.create(
            name="集成测试工序",
            code="INT_PROC",
            artwork_required=False,
            die_required=False,
            foiling_plate_required=False,
            embossing_plate_required=False,
        )
        self.product.default_processes.add(self.process)
        self.sales_order = SalesOrder.objects.create(
            order_number="SOINT001",
            customer=self.customer,
            order_date=timezone.now().date(),
            delivery_date=timezone.now().date() + timedelta(days=10),
            total_amount=5000.0,
            status="confirmed",
            created_by=self.user,
        )
        SalesOrderItem.objects.create(
            sales_order=self.sales_order,
            product=self.product,
            quantity=100,
            unit_price=50.0,
        )

    def test_complete_flow_from_sales_order_to_completion(self):
        """测试完整流程：从销售订单到施工单完成"""
        # 1. 从销售订单创建施工单
        work_order = WorkOrderFlowService.create_from_sales_order(
            sales_order_id=self.sales_order.id,
            production_quantity=100,
            delivery_date=timezone.now().date() + timedelta(days=10),
            priority="normal",
            notes="集成测试",
            created_by=self.user,
        )
        self.assertEqual(work_order.status, "pending")

        # 2. 提交审核
        work_order = WorkOrderFlowService.submit_for_approval(
            work_order_id=work_order.id,
            submitted_by=self.user,
        )
        self.assertEqual(work_order.approval_status, "pending")

        # 3. 审核通过（自动分派任务）
        work_order = WorkOrderFlowService.handle_approval_passed(
            work_order=work_order,
            approved_by=self.user,
            comment="审核通过",
        )
        self.assertEqual(work_order.approval_status, "approved")
        self.assertEqual(work_order.status, "in_progress")

        # 4. 完成所有任务
        WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order
        ).update(status="completed")

        # 5. 检查并完成施工单
        is_completed = WorkOrderFlowService.check_and_complete_workorder(
            work_order=work_order
        )
        self.assertTrue(is_completed)
        self.assertEqual(work_order.status, "completed")

        # 完整流程验证成功！
        self.assertTrue(True)
