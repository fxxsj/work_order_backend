"""
API 端点测试
测试 REST API 端点的功能
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from .conftest import TestDataFactory, APITestCaseMixin
from ..models import WorkOrder, Customer, Product, Process
import json


class WorkOrderAPITest(APITestCaseMixin, TestCase):
    """施工单 API 测试"""

    def setUp(self):
        """设置测试数据"""
        super().setUp()
        self.user = TestDataFactory.create_user()
        self.client.force_login(self.user)
        self.customer = TestDataFactory.create_customer(salesperson=self.user)
        self.product = TestDataFactory.create_product()
        self.process = Process.objects.create(name='测试工序', code='TEST')

    def test_list_workorders(self):
        """测试获取施工单列表"""
        # 创建施工单
        TestDataFactory.create_workorder(
            customer=self.customer,
            creator=self.user
        )

        # 获取列表
        response = self.api_get('/api/workorders/', user=self.user)

        # 应该成功
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data['results']), 0)

    def test_create_workorder(self):
        """测试创建施工单"""
        data = {
            'customer': self.customer.id,
            'production_quantity': 100,
            'delivery_date': '2026-12-31',
            'products_data': [
                {
                    'product': self.product.id,
                    'quantity': 50,
                    'unit': '件'
                }
            ],
            'processes': [self.process.id]  # 工序ID列表
        }

        response = self.api_post('/api/workorders/', data, user=self.user)

        # 应该成功创建
        self.assertEqual(response.status_code, 201)
        self.assertIn('order_number', response.data)

    def test_get_workorder_detail(self):
        """测试获取施工单详情"""
        work_order = TestDataFactory.create_workorder(
            customer=self.customer,
            creator=self.user
        )

        response = self.api_get(f'/api/workorders/{work_order.id}/', user=self.user)

        # 应该成功
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], work_order.id)

    def test_update_workorder(self):
        """测试更新施工单"""
        work_order = TestDataFactory.create_workorder(
            customer=self.customer,
            creator=self.user,
            status='pending'
        )

        data = {
            'production_quantity': 200,
            'notes': '更新备注'
        }

        response = self.api_patch(f'/api/workorders/{work_order.id}/', data, user=self.user)

        # 应该成功
        self.assertEqual(response.status_code, 200)

    def test_delete_workorder(self):
        """测试删除施工单"""
        work_order = TestDataFactory.create_workorder(
            customer=self.customer,
            creator=self.user,
            status='pending'
        )

        response = self.api_delete(f'/api/workorders/{work_order.id}/', user=self.user)

        # 应该成功
        self.assertEqual(response.status_code, 204)

        # 验证已删除
        self.assertFalse(WorkOrder.objects.filter(id=work_order.id).exists())

    def test_unauthenticated_access_denied(self):
        """测试未认证访问被拒绝"""
        # 登出
        self.client.logout()

        response = self.api_get('/api/workorders/')

        # 应该返回 401 或 403（取决于 DRF 配置）
        self.assertIn(response.status_code, [401, 403])

    def test_filter_by_status(self):
        """测试按状态过滤"""
        # 清空现有的施工单
        from workorder.models.core import WorkOrder
        WorkOrder.objects.all().delete()

        # 创建不同状态的施工单（都由同一个用户创建）
        wo1 = TestDataFactory.create_workorder(
            customer=self.customer,
            creator=self.user
        )
        wo1.status = 'pending'
        wo1.save()

        wo2 = TestDataFactory.create_workorder(
            customer=self.customer,
            creator=self.user
        )
        wo2.status = 'in_progress'
        wo2.save()

        # 验证数据库中的状态
        pending_count = WorkOrder.objects.filter(status='pending').count()
        in_progress_count = WorkOrder.objects.filter(status='in_progress').count()
        print(f"数据库中: pending={pending_count}, in_progress={in_progress_count}")

        # 过滤待开始的施工单
        response = self.api_get('/api/workorders/?status=pending', user=self.user)

        # 调试：打印结果
        print(f"API过滤后的施工单数量: {len(response.data['results'])}")
        for i, wo in enumerate(response.data['results']):
            print(f"  {i+1}. ID={wo['id']}, order_number={wo['order_number']}, status={wo['status']}")

        # 应该只返回待开始的
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'pending')

    def test_search_by_order_number(self):
        """测试按施工单号搜索"""
        work_order = TestDataFactory.create_workorder(
            customer=self.customer,
            creator=self.user
        )

        # 搜索施工单号
        response = self.api_get(f'/api/workorders/?search={work_order.order_number}', user=self.user)

        # 应该找到
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data['results']), 0)


class WorkOrderProcessAPITest(APITestCaseMixin, TestCase):
    """工序 API 测试"""

    def setUp(self):
        """设置测试数据"""
        super().setUp()
        self.user = TestDataFactory.create_user()
        self.client.force_login(self.user)
        self.customer = TestDataFactory.create_customer(salesperson=self.user)
        self.work_order = TestDataFactory.create_workorder(
            customer=self.customer,
            creator=self.user
        )
        self.process = Process.objects.create(name='测试工序', code='TEST')

    def test_list_processes(self):
        """测试获取工序列表"""
        wo_process = TestDataFactory.create_workorder_process(
            work_order=self.work_order,
            process=self.process
        )

        response = self.api_get(f'/api/workorder-processes/?work_order={self.work_order.id}', user=self.user)

        # 应该成功
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data['results']), 0)

    def test_start_process(self):
        """测试开始工序"""
        from ..models import WorkOrderProcess

        wo_process = WorkOrderProcess.objects.create(
            work_order=self.work_order,
            process=self.process,
            sequence=10
        )

        response = self.api_post(f'/api/workorder-processes/{wo_process.id}/start/', user=self.user)

        # 应该成功
        self.assertEqual(response.status_code, 200)

        # 验证状态已更新
        wo_process.refresh_from_db()
        self.assertEqual(wo_process.status, 'in_progress')

    def test_batch_start_processes(self):
        """测试批量开始工序"""
        from ..models import WorkOrderProcess

        process1 = Process.objects.create(name='工序1', code='P1')
        process2 = Process.objects.create(name='工序2', code='P2')

        wo_process1 = WorkOrderProcess.objects.create(
            work_order=self.work_order,
            process=process1,
            sequence=10
        )
        wo_process2 = WorkOrderProcess.objects.create(
            work_order=self.work_order,
            process=process2,
            sequence=20
        )

        data = {
            'process_ids': [wo_process1.id, wo_process2.id]
        }

        response = self.api_post('/api/workorder-processes/batch_start/', data, user=self.user)

        # 应该成功
        self.assertEqual(response.status_code, 200)


class WorkOrderTaskAPITest(APITestCaseMixin, TestCase):
    """任务 API 测试"""

    def setUp(self):
        """设置测试数据"""
        super().setUp()
        self.user = TestDataFactory.create_user()
        self.client.force_login(self.user)
        self.customer = TestDataFactory.create_customer(salesperson=self.user)
        self.work_order = TestDataFactory.create_workorder(
            customer=self.customer,
            creator=self.user
        )
        self.process = Process.objects.create(name='测试工序', code='TEST')

    def test_list_tasks(self):
        """测试获取任务列表"""
        from ..models import WorkOrderProcess, WorkOrderTask

        wo_process = WorkOrderProcess.objects.create(
            work_order=self.work_order,
            process=self.process,
            sequence=10
        )

        task = WorkOrderTask.objects.create(
            work_order_process=wo_process,
            task_type='general',
            work_content='测试任务',
            production_quantity=100
        )

        response = self.api_get(f'/api/workorder-tasks/?work_order_process={wo_process.id}', user=self.user)

        # 应该成功
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data['results']), 0)

    def test_update_task_quantity(self):
        """测试更新任务数量"""
        from ..models import WorkOrderProcess, WorkOrderTask

        wo_process = WorkOrderProcess.objects.create(
            work_order=self.work_order,
            process=self.process,
            sequence=10
        )

        task = WorkOrderTask.objects.create(
            work_order_process=wo_process,
            task_type='general',
            work_content='测试任务',
            production_quantity=100,
            quantity_completed=50
        )

        data = {
            'quantity_increment': 30
        }

        response = self.api_post(f'/api/workorder-tasks/{task.id}/update_quantity/', data, user=self.user)

        # 应该成功
        self.assertEqual(response.status_code, 200)

        # 验证数量已更新
        task.refresh_from_db()
        self.assertEqual(task.quantity_completed, 80)

    def test_complete_task(self):
        """测试完成任务"""
        from ..models import WorkOrderProcess, WorkOrderTask

        wo_process = WorkOrderProcess.objects.create(
            work_order=self.work_order,
            process=self.process,
            sequence=10
        )

        task = WorkOrderTask.objects.create(
            work_order_process=wo_process,
            task_type='general',
            work_content='测试任务',
            production_quantity=100,
            quantity_completed=80
        )

        response = self.api_post(f'/api/workorder-tasks/{task.id}/complete/', user=self.user)

        # 应该成功
        self.assertEqual(response.status_code, 200)

        # 验证任务已完成
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
        self.assertEqual(task.quantity_completed, 100)

    def test_assign_task(self):
        """测试分派任务"""
        from ..models import WorkOrderProcess, WorkOrderTask, Department

        wo_process = WorkOrderProcess.objects.create(
            work_order=self.work_order,
            process=self.process,
            sequence=10
        )

        task = WorkOrderTask.objects.create(
            work_order_process=wo_process,
            task_type='general',
            work_content='测试任务',
            production_quantity=100
        )

        department, _ = Department.objects.get_or_create(
            code='TEST',
            defaults={'name': '测试部门'}
        )

        data = {
            'assigned_department': department.id,
            'assigned_operator': self.user.id
        }

        response = self.api_post(f'/api/workorder-tasks/{task.id}/assign/', data, user=self.user)

        # 应该成功
        self.assertEqual(response.status_code, 200)

        # 验证已分派
        task.refresh_from_db()
        self.assertEqual(task.assigned_department, department)


def create_workorder_process(work_order, process, sequence=10):
    """辅助函数：创建施工单工序"""
    from ..models import WorkOrderProcess
    return WorkOrderProcess.objects.create(
        work_order=work_order,
        process=process,
        sequence=sequence
    )
