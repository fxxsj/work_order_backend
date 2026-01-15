"""
权限系统测试
测试数据权限和操作权限
"""
from django.test import TestCase
from django.contrib.auth.models import User, Group
from rest_framework.test import APIClient
from .conftest import TestDataFactory, APITestCaseMixin
from ..models import WorkOrder, Customer, Product, Process, Department


class WorkOrderDataPermissionTest(APITestCaseMixin, TestCase):
    """施工单数据权限测试"""

    def setUp(self):
        """设置测试数据"""
        # 创建业务员1和业务员2
        self.salesperson1 = TestDataFactory.create_user(username='sales1')
        self.salesperson2 = TestDataFactory.create_user(username='sales2')

        # 创建客户1（属于业务员1）和客户2（属于业务员2）
        self.customer1 = TestDataFactory.create_customer(
            name='客户1',
            salesperson=self.salesperson1
        )
        self.customer2 = TestDataFactory.create_customer(
            name='客户2',
            salesperson=self.salesperson2
        )

        # 创建施工单
        self.wo1 = TestDataFactory.create_workorder(
            customer=self.customer1,
            creator=self.salesperson1
        )
        self.wo2 = TestDataFactory.create_workorder(
            customer=self.customer2,
            creator=self.salesperson2
        )

        # 创建部门
        self.department = Department.objects.create(
            name='生产部',
            code='PROD'
        )

        # 创建生产主管
        self.supervisor = TestDataFactory.create_user(username='supervisor')
        self.supervisor_profile = self.supervisor.profile
        self.supervisor_profile.departments.add(self.department)

    def test_salesperson_can_only_see_own_customers(self):
        """测试业务员只能看到自己负责的客户施工单"""
        # 以业务员1登录
        self.client.force_login(self.salesperson1)

        # 获取施工单列表
        response = self.api_get('/api/workorders/')

        # 应该只看到客户1的施工单
        self.assertEqual(response.status_code, 200)
        workorder_ids = [wo['id'] for wo in response.data['results']]
        self.assertIn(self.wo1.id, workorder_ids)
        self.assertNotIn(self.wo2.id, workorder_ids)

    def test_salesperson_can_create_own_customer_workorder(self):
        """测试业务员可以为自己负责的客户创建施工单"""
        self.client.force_login(self.salesperson1)

        data = {
            'customer': self.customer1.id,
            'production_quantity': 100,
            'delivery_date': '2026-12-31'
        }

        response = self.api_post('/api/workorders/', data)

        # 应该成功
        self.assertEqual(response.status_code, 201)

    def test_salesperson_cannot_create_other_customer_workorder(self):
        """测试业务员不能为其他业务员的客户创建施工单"""
        self.client.force_login(self.salesperson1)

        data = {
            'customer': self.customer2.id,  # 客户2属于业务员2
            'production_quantity': 100,
            'delivery_date': '2026-12-31'
        }

        response = self.api_post('/api/workorders/', data)

        # 应该被拒绝（权限不足）
        self.assertIn(response.status_code, [403, 400])

    def test_supervisor_can_see_department_related_orders(self):
        """测试生产主管可以看到相关部门的施工单"""
        # TODO: 实现生产主管可以看到相关部门任务时的测试
        pass


class WorkOrderTaskPermissionTest(APITestCaseMixin, TestCase):
    """任务操作权限测试"""

    def setUp(self):
        """设置测试数据"""
        # 创建用户
        self.operator1 = TestDataFactory.create_user(username='op1')
        self.operator2 = TestDataFactory.create_user(username='op2')
        self.supervisor = TestDataFactory.create_user(username='sup')

        # 创建部门和施工单
        self.department = Department.objects.create(
            name='生产一部',
            code='DEPT1'
        )
        self.customer = TestDataFactory.create_customer(salesperson=self.supervisor)
        self.work_order = TestDataFactory.create_workorder(
            customer=self.customer,
            creator=self.supervisor
        )
        self.process = Process.objects.create(name='测试工序', code='TEST')

    def test_operator_can_only_update_own_tasks(self):
        """测试操作员只能更新自己分派的任务"""
        from ..models import WorkOrderProcess, WorkOrderTask

        wo_process = WorkOrderProcess.objects.create(
            work_order=self.work_order,
            process=self.process,
            sequence=10
        )

        # 创建任务1（分派给操作员1）和任务2（分派给操作员2）
        task1 = WorkOrderTask.objects.create(
            work_order_process=wo_process,
            task_type='general',
            work_content='任务1',
            production_quantity=100,
            assigned_operator=self.operator1
        )

        task2 = WorkOrderTask.objects.create(
            work_order_process=wo_process,
            task_type='general',
            work_content='任务2',
            production_quantity=100,
            assigned_operator=self.operator2
        )

        # 操作员1登录
        self.client.force_login(self.operator1)

        # 可以更新自己的任务
        data = {'increment': 10}
        response = self.api_post(f'/api/workorder-tasks/{task1.id}/update_quantity/', data)
        self.assertEqual(response.status_code, 200)

        # 不能更新别人的任务
        response = self.api_post(f'/api/workorder-tasks/{task2.id}/update_quantity/', data)
        self.assertIn(response.status_code, [403, 404])

    def test_supervisor_can_update_department_tasks(self):
        """测试生产主管可以更新部门内所有任务"""
        from ..models import WorkOrderProcess, WorkOrderTask

        wo_process = WorkOrderProcess.objects.create(
            work_order=self.work_order,
            process=self.process,
            sequence=10,
            department=self.department
        )

        # 创建部门任务
        task = WorkOrderTask.objects.create(
            work_order_process=wo_process,
            task_type='general',
            work_content='部门任务',
            production_quantity=100,
            assigned_department=self.department
        )

        # 生产主管登录
        self.client.force_login(self.supervisor)

        # 应该可以更新部门任务
        data = {'increment': 10}
        response = self.api_post(f'/api/workorder-tasks/{task.id}/update_quantity/', data)
        self.assertEqual(response.status_code, 200)


class ApprovalPermissionTest(APITestCaseMixin, TestCase):
    """审核权限测试"""

    def setUp(self):
        """设置测试数据"""
        # 创建业务员1和业务员2
        self.salesperson1 = TestDataFactory.create_user(username='sales1')
        self.salesperson2 = TestDataFactory.create_user(username='sales2')

        # 创建客户
        self.customer1 = TestDataFactory.create_customer(
            salesperson=self.salesperson1
        )
        self.customer2 = TestDataFactory.create_customer(
            salesperson=self.salesperson2
        )

        # 创建待审核的施工单
        self.wo1 = TestDataFactory.create_workorder(
            customer=self.customer1,
            creator=self.salesperson1
        )

        # 添加产品和工序以满足审核条件
        from ..models import WorkOrderProduct
        product = TestDataFactory.create_product()
        WorkOrderProduct.objects.create(
            work_order=self.wo1,
            product=product,
            quantity=50
        )

    def test_salesperson_can_approve_own_customer_orders(self):
        """测试业务员可以审核自己负责客户的施工单"""
        self.client.force_login(self.salesperson1)

        # 审核施工单
        response = self.api_post(f'/api/workorders/{self.wo1.id}/approve/', {
            'approved': True
        })

        # 应该成功
        self.assertEqual(response.status_code, 200)

        # 验证状态已更新
        self.wo1.refresh_from_db()
        self.assertEqual(self.wo1.approval_status, 'approved')

    def test_salesperson_cannot_approve_other_customer_orders(self):
        """测试业务员不能审核其他业务员客户的施工单"""
        self.client.force_login(self.salesperson2)

        # 尝试审核施工单
        response = self.api_post(f'/api/workorders/{self.wo1.id}/approve/', {
            'approved': True
        })

        # 应该被拒绝
        self.assertIn(response.status_code, [403, 400])

    def test_rejection_requires_reason(self):
        """测试拒绝时必须填写原因"""
        self.client.force_login(self.salesperson1)

        # 拒绝但未填写原因
        response = self.api_post(f'/api/workorders/{self.wo1.id}/approve/', {
            'approved': False
        })

        # 应该失败（缺少原因）
        self.assertIn(response.status_code, [400, 403])

        # 拒绝并填写原因
        response = self.api_post(f'/api/workorders/{self.wo1.id}/approve/', {
            'approved': False,
            'rejection_reason': '信息不完整'
        })

        # 应该成功
        self.assertEqual(response.status_code, 200)

        # 验证状态
        self.wo1.refresh_from_db()
        self.assertEqual(self.wo1.approval_status, 'rejected')


class APIAuthenticationTest(TestCase):
    """API 认证测试"""

    def setUp(self):
        """设置测试数据"""
        self.client = APIClient()

    def test_login_required(self):
        """测试需要登录"""
        response = self.client.get('/api/workorders/')

        # 未登录应该返回 401
        self.assertEqual(response.status_code, 401)

    def test_login_success(self):
        """测试登录成功"""
        user = TestDataFactory.create_user()

        response = self.client.post('/api/auth/login/', {
            'username': user.username,
            'password': 'testpass123'
        })

        # 应该成功
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['username'], user.username)

    def test_login_wrong_password(self):
        """测试密码错误"""
        TestDataFactory.create_user()

        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'wrongpassword'
        })

        # 应该失败
        self.assertEqual(response.status_code, 401)

    def test_logout(self):
        """测试登出"""
        user = TestDataFactory.create_user()

        # 先登录
        self.client.force_login(user)

        # 登出
        response = self.client.post('/api/auth/logout/')

        # 应该成功
        self.assertEqual(response.status_code, 200)

    def test_get_current_user(self):
        """测试获取当前用户"""
        user = TestDataFactory.create_user()

        # 登录
        self.client.force_login(user)

        # 获取当前用户
        response = self.client.get('/api/auth/user/')

        # 应该成功
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], user.id)
        self.assertEqual(response.data['username'], user.username)
