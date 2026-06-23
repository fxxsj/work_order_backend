"""
API 端点测试
测试 REST API 端点的功能
"""

from django.test import TestCase
from rest_framework import status
from .conftest import TestDataFactory, APITestCaseMixin
from ..models import WorkOrder, Process, Artwork
from ..models.sales import SalesOrder, SalesOrderItem


class WorkOrderAPITest(APITestCaseMixin, TestCase):
    """施工单 API 测试"""

    def setUp(self):
        """设置测试数据"""
        super().setUp()
        self.user = TestDataFactory.create_user()
        self.admin_user = TestDataFactory.create_user(
            username="adminuser", is_superuser=True
        )
        self.client.force_login(self.user)
        self.customer = TestDataFactory.create_customer(salesperson=self.user)
        self.product = TestDataFactory.create_product()
        self.process = Process.objects.create(name="测试工序", code="TEST")
        self.sales_order = SalesOrder.objects.create(
            customer=self.customer,
            order_date="2026-01-01",
            delivery_date="2026-12-31",
            status="approved",
            created_by=self.user,
        )
        self.sales_order_item = SalesOrderItem.objects.create(
            sales_order=self.sales_order,
            product=self.product,
            quantity=100,
            unit="件",
            unit_price=10,
        )

    def test_list_workorders(self):
        """测试获取施工单列表"""
        # 创建施工单
        TestDataFactory.create_workorder(
            customer=self.customer, creator=self.user
        )

        # 获取列表
        response = self.api_get("/api/v1/workorders/", user=self.user)

        # 应该成功
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["data"]["results"]), 0)

    def test_create_workorder(self):
        """测试创建施工单"""
        data = {
            "customer": self.customer.id,
            "production_quantity": 100,
            "delivery_date": "2026-12-31",
            "products_data": [
                {"product": self.product.id, "quantity": 50, "unit": "件"}
            ],
            "processes": [self.process.id],  # 工序ID列表
        }

        response = self.api_post("/api/v1/workorders/", data, user=self.user)

        # 应该成功创建
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("order_number", response.data["data"])

    def test_create_workorder_with_split_sales_order_item_quantity(self):
        """测试手工创建施工单时允许同一订单明细拆量开单。"""
        first_payload = {
            "customer": self.customer.id,
            "sales_order": self.sales_order.id,
            "production_quantity": 60,
            "delivery_date": "2026-12-31",
            "products_data": [
                {
                    "product": self.product.id,
                    "quantity": 60,
                    "unit": "件",
                    "source_type": "sales_order",
                    "sales_order_item": self.sales_order_item.id,
                }
            ],
            "processes": [self.process.id],
        }
        second_payload = {
            "customer": self.customer.id,
            "sales_order": self.sales_order.id,
            "production_quantity": 40,
            "delivery_date": "2026-12-31",
            "products_data": [
                {
                    "product": self.product.id,
                    "quantity": 40,
                    "unit": "件",
                    "source_type": "sales_order",
                    "sales_order_item": self.sales_order_item.id,
                }
            ],
            "processes": [self.process.id],
        }

        first_response = self.api_post(
            "/api/v1/workorders/", first_payload, user=self.user
        )
        second_response = self.api_post(
            "/api/v1/workorders/", second_payload, user=self.user
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)

    def test_create_workorder_rejects_over_allocated_sales_order_item_quantity(
        self,
    ):
        """测试手工创建施工单时超出订单明细剩余可开数量会被拒绝。"""
        first_payload = {
            "customer": self.customer.id,
            "sales_order": self.sales_order.id,
            "production_quantity": 60,
            "delivery_date": "2026-12-31",
            "products_data": [
                {
                    "product": self.product.id,
                    "quantity": 60,
                    "unit": "件",
                    "source_type": "sales_order",
                    "sales_order_item": self.sales_order_item.id,
                }
            ],
            "processes": [self.process.id],
        }
        over_payload = {
            "customer": self.customer.id,
            "sales_order": self.sales_order.id,
            "production_quantity": 50,
            "delivery_date": "2026-12-31",
            "products_data": [
                {
                    "product": self.product.id,
                    "quantity": 50,
                    "unit": "件",
                    "source_type": "sales_order",
                    "sales_order_item": self.sales_order_item.id,
                }
            ],
            "processes": [self.process.id],
        }

        first_response = self.api_post(
            "/api/v1/workorders/", first_payload, user=self.user
        )
        over_response = self.api_post(
            "/api/v1/workorders/", over_payload, user=self.user
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            over_response.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertIn("products_data", over_response.data["errors"])

    def test_sales_order_candidates_include_remaining_quantity(self):
        """测试施工单来源订单候选接口返回剩余可开数量。"""
        WorkOrder.objects.create(
            customer=self.customer,
            sales_order=self.sales_order,
            production_quantity=60,
            delivery_date="2026-12-31",
            created_by=self.user,
            manager=self.user,
        ).products.create(
            product=self.product,
            quantity=60,
            unit="件",
            source_type="sales_order",
            sales_order_item=self.sales_order_item,
        )

        response = self.api_get(
            "/api/v1/workorders/sales_order_candidates/", user=self.user
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        candidates = response.data["data"]
        self.assertEqual(len(candidates), 1)
        available_products = candidates[0]["available_products"]
        self.assertEqual(len(available_products), 1)
        self.assertEqual(available_products[0]["allocated_quantity"], 60)
        self.assertEqual(available_products[0]["remaining_quantity"], 40)

    def test_get_workorder_detail(self):
        """测试获取施工单详情"""
        work_order = TestDataFactory.create_workorder(
            customer=self.customer, creator=self.user
        )

        response = self.api_get(
            f"/api/v1/workorders/{work_order.id}/", user=self.user
        )

        # 应该成功
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["id"], work_order.id)

    def test_get_workorder_detail_with_expand(self):
        """测试使用 ?expand= 控制详情返回字段"""
        work_order = TestDataFactory.create_workorder(
            customer=self.customer, creator=self.user
        )

        # 默认请求包含所有字段
        full_response = self.api_get(
            f"/api/v1/workorders/{work_order.id}/", user=self.user
        )
        self.assertIn("products", full_response.data["data"])
        self.assertIn("order_processes", full_response.data["data"])

        # 仅展开 assets 和 progress
        partial_response = self.api_get(
            f"/api/v1/workorders/{work_order.id}/",
            user=self.user,
            data={"expand": "assets,progress"},
        )
        self.assertEqual(partial_response.status_code, status.HTTP_200_OK)
        data = partial_response.data["data"]
        self.assertIn("progress_percentage", data)
        self.assertIn("artwork_names", data)
        self.assertNotIn("products", data)
        self.assertNotIn("order_processes", data)

    def test_update_workorder(self):
        """测试更新施工单"""
        work_order = TestDataFactory.create_workorder(
            customer=self.customer, creator=self.user, status="pending"
        )
        # 添加产品和工序以满足数据完整性验证
        work_order.products.create(
            product=self.product, quantity=100, unit="件", source_type="stock"
        )
        work_order.order_processes.create(process=self.process, sequence=10)

        data = {"production_quantity": 200, "notes": "更新备注"}

        response = self.api_patch(
            f"/api/v1/workorders/{work_order.id}/", data, user=self.user
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_workorder_syncs_m2m_and_products(self):
        """测试创建施工单时正确同步 M2M 版关系与产品"""
        artwork = Artwork.objects.create(name="测试图稿")
        data = {
            "customer": self.customer.id,
            "production_quantity": 100,
            "delivery_date": "2026-12-31",
            "products_data": [
                {"product": self.product.id, "quantity": 50, "unit": "件"}
            ],
            "processes": [self.process.id],
            "artworks": [artwork.id],
        }

        response = self.api_post("/api/v1/workorders/", data, user=self.user)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        work_order = WorkOrder.objects.get(id=response.data["data"]["id"])
        self.assertIn(artwork, work_order.artworks.all())
        self.assertEqual(work_order.products.count(), 1)

    def test_update_workorder_preserves_m2m_when_not_sent(self):
        """测试更新施工单时未发送 M2M 字段应保持原关系"""
        artwork = Artwork.objects.create(name="测试图稿")
        work_order = TestDataFactory.create_workorder(
            customer=self.customer, creator=self.user, status="pending"
        )
        work_order.products.create(
            product=self.product, quantity=100, unit="件", source_type="stock"
        )
        work_order.order_processes.create(process=self.process, sequence=10)
        work_order.artworks.add(artwork)

        data = {"production_quantity": 200, "notes": "更新备注但不修改图稿"}

        response = self.api_patch(
            f"/api/v1/workorders/{work_order.id}/", data, user=self.user
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        work_order.refresh_from_db()
        self.assertIn(artwork, work_order.artworks.all())

    def test_delete_workorder(self):
        """测试删除施工单"""
        work_order = TestDataFactory.create_workorder(
            customer=self.customer, creator=self.user, status="pending"
        )

        response = self.api_delete(
            f"/api/v1/workorders/{work_order.id}/", user=self.admin_user
        )

        # 删除成功返回 204 No Content
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # 验证已删除
        self.assertFalse(WorkOrder.objects.filter(id=work_order.id).exists())

    def test_unauthenticated_access_denied(self):
        """测试未认证访问被拒绝"""
        # 登出
        self.client.logout()

        response = self.api_get("/api/v1/workorders/")

        # 应该返回 401 或 403（取决于 DRF 配置）
        self.assertIn(response.status_code, [401, 403])

    def test_filter_by_status(self):
        """测试按状态过滤"""
        # 清空现有的施工单
        from workorder.models.core import WorkOrder

        WorkOrder.objects.all().delete()

        # 创建不同状态的施工单（都由同一个用户创建）
        wo1 = TestDataFactory.create_workorder(
            customer=self.customer, creator=self.user
        )
        wo1.status = "pending"
        wo1.save()

        wo2 = TestDataFactory.create_workorder(
            customer=self.customer, creator=self.user
        )
        wo2.status = "in_progress"
        wo2.save()

        # 验证数据库中的状态
        _ = WorkOrder.objects.filter(status="pending").count()
        _ = WorkOrder.objects.filter(
            status="in_progress"
        ).count()

        # 过滤待开始的施工单
        response = self.api_get(
            "/api/v1/workorders/?status=pending", user=self.user
        )

        # 调试输出已清理

        # 应该只返回待开始的
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["results"]), 1)
        self.assertEqual(
            response.data["data"]["results"][0]["status"], "pending"
        )

    def test_search_by_order_number(self):
        """测试按施工单号搜索"""
        work_order = TestDataFactory.create_workorder(
            customer=self.customer, creator=self.user
        )

        # 搜索施工单号
        response = self.api_get(
            f"/api/v1/workorders/?search={work_order.order_number}",
            user=self.user,
        )

        # 应该找到
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["data"]["results"]), 0)


class WorkOrderProcessAPITest(APITestCaseMixin, TestCase):
    """工序 API 测试"""

    def setUp(self):
        """设置测试数据"""
        super().setUp()
        self.user = TestDataFactory.create_user()
        self.client.force_login(self.user)
        self.customer = TestDataFactory.create_customer(salesperson=self.user)
        self.work_order = TestDataFactory.create_workorder(
            customer=self.customer, creator=self.user
        )
        self.process = Process.objects.create(name="测试工序", code="TEST")

    def test_list_processes(self):
        """测试获取工序列表"""
        _ = TestDataFactory.create_workorder_process(
            work_order=self.work_order, process=self.process
        )

        response = self.api_get(
            f"/api/v1/workorder-processes/?work_order={self.work_order.id}",
            user=self.user,
        )

        # 应该成功
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["data"]["results"]), 0)

    def test_start_process(self):
        """测试开始工序"""
        from ..models import WorkOrderProcess

        wo_process = WorkOrderProcess.objects.create(
            work_order=self.work_order, process=self.process, sequence=10
        )

        response = self.api_post(
            f"/api/v1/workorder-processes/{wo_process.id}/start/",
            user=self.user,
        )

        # 应该成功
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 验证状态已更新
        wo_process.refresh_from_db()
        self.assertEqual(wo_process.status, "in_progress")

    def test_batch_start_processes(self):
        """测试批量开始工序"""
        from ..models import WorkOrderProcess

        process1 = Process.objects.create(name="工序1", code="P1")
        process2 = Process.objects.create(name="工序2", code="P2")

        wo_process1 = WorkOrderProcess.objects.create(
            work_order=self.work_order, process=process1, sequence=10
        )
        wo_process2 = WorkOrderProcess.objects.create(
            work_order=self.work_order, process=process2, sequence=20
        )

        data = {"process_ids": [wo_process1.id, wo_process2.id]}

        response = self.api_post(
            "/api/v1/workorder-processes/batch_start/", data, user=self.user
        )

        # 应该成功
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class WorkOrderTaskAPITest(APITestCaseMixin, TestCase):
    """任务 API 测试"""

    def setUp(self):
        """设置测试数据"""
        super().setUp()
        self.user = TestDataFactory.create_user()
        self.admin_user = TestDataFactory.create_user(
            username="wotask_admin", is_superuser=True
        )
        self.client.force_login(self.user)
        self.customer = TestDataFactory.create_customer(salesperson=self.user)
        self.work_order = TestDataFactory.create_workorder(
            customer=self.customer, creator=self.user
        )
        self.process = Process.objects.create(name="测试工序", code="TEST")

    def test_list_tasks(self):
        """测试获取任务列表"""
        from ..models import WorkOrderProcess, WorkOrderTask

        wo_process = WorkOrderProcess.objects.create(
            work_order=self.work_order, process=self.process, sequence=10
        )

        _ = WorkOrderTask.objects.create(
            work_order_process=wo_process,
            task_type="general",
            work_content="测试任务",
            production_quantity=100,
        )

        response = self.api_get(
            f"/api/v1/workorder-tasks/?work_order_process={wo_process.id}",
            user=self.user,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["data"]["results"]), 0)

    def test_update_task_quantity(self):
        """测试更新任务数量"""
        from ..models import WorkOrderProcess, WorkOrderTask

        wo_process = WorkOrderProcess.objects.create(
            work_order=self.work_order, process=self.process, sequence=10
        )

        task = WorkOrderTask.objects.create(
            work_order_process=wo_process,
            task_type="general",
            work_content="测试任务",
            production_quantity=100,
            quantity_completed=50,
        )

        data = {"quantity_increment": 30}

        response = self.api_post(
            f"/api/v1/workorder-tasks/{task.id}/update_quantity/",
            data,
            user=self.user,
        )

        # 应该成功
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 验证数量已更新
        task.refresh_from_db()
        self.assertEqual(task.quantity_completed, 80)

    def test_complete_task(self):
        """测试完成任务"""
        from ..models import WorkOrderProcess, WorkOrderTask

        wo_process = WorkOrderProcess.objects.create(
            work_order=self.work_order, process=self.process, sequence=10
        )

        task = WorkOrderTask.objects.create(
            work_order_process=wo_process,
            task_type="general",
            work_content="测试任务",
            production_quantity=100,
            quantity_completed=80,
        )

        response = self.api_post(
            f"/api/v1/workorder-tasks/{task.id}/complete/", user=self.user
        )

        # 应该成功
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 验证任务已完成
        task.refresh_from_db()
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.quantity_completed, 100)

    def test_assign_task(self):
        """测试分派任务"""
        from ..models import WorkOrderProcess, WorkOrderTask, Department

        wo_process = WorkOrderProcess.objects.create(
            work_order=self.work_order, process=self.process, sequence=10
        )

        department, _ = Department.objects.get_or_create(
            code="TEST", defaults={"name": "测试部门"}
        )
        department.processes.add(self.process)

        task = WorkOrderTask.objects.create(
            work_order_process=wo_process,
            task_type="general",
            work_content="测试任务",
            production_quantity=100,
            assigned_department=department,
        )

        # 给 admin_user 创建 UserProfile 并加入部门（满足 assign_to_operator 的部门检查）
        from workorder.models.system import UserProfile

        profile, _ = UserProfile.objects.get_or_create(user=self.admin_user)
        profile.departments.add(department)

        data = {
            "assigned_department": department.id,
            "assigned_operator": self.admin_user.id,
        }

        response = self.api_post(
            f"/api/v1/workorder-tasks/{task.id}/assign/",
            data,
            user=self.admin_user,
        )

        # 应该成功
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 验证已分派
        task.refresh_from_db()
        self.assertEqual(task.assigned_department, department)


def create_workorder_process(work_order, process, sequence=10):
    """辅助函数：创建施工单工序"""
    from ..models import WorkOrderProcess

    return WorkOrderProcess.objects.create(
        work_order=work_order, process=process, sequence=sequence
    )
