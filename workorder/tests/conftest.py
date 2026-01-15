"""
测试配置文件
定义测试共享配置和工具
"""
import os
from django.conf import settings
from django.test.utils import get_runner

# 测试数据库配置
TEST_DATABASE = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',  # 使用内存数据库加快测试速度
        'ATOMIC_REQUESTS': True,
    }
}

# 测试时覆盖的设置
TEST_SETTINGS_OVERRIDE = {
    # 使用密码哈希器加速测试
    'PASSWORD_HASHERS': [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ],
    # 禁用调试
    'DEBUG': False,
    # 测试时禁用日志
    'LOGGING': {},
    # 测试邮箱后端
    'EMAIL_BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
}


def configure_test_settings():
    """配置测试环境设置"""
    if not settings.configured:
        settings.configure(**TEST_SETTINGS_OVERRIDE)


def get_test_runner_wrapper():
    """获取测试运行器包装器"""
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False, keepdb=False)
    return test_runner


class TestDataFactory:
    """测试数据工厂 - 快速创建测试数据"""

    @staticmethod
    def create_user(username='testuser', password='testpass123', **kwargs):
        """创建测试用户"""
        from django.contrib.auth.models import User
        return User.objects.create_user(
            username=username,
            password=password,
            email=kwargs.get('email', f'{username}@example.com'),
            first_name=kwargs.get('first_name', 'Test'),
            last_name=kwargs.get('last_name', 'User'),
            is_staff=kwargs.get('is_staff', False),
            is_superuser=kwargs.get('is_superuser', False),
        )

    @staticmethod
    def create_customer(name='测试客户', salesperson=None, **kwargs):
        """创建测试客户"""
        from workorder.models.base import Customer
        return Customer.objects.create(
            name=name,
            contact_person=kwargs.get('contact_person', '张三'),
            phone=kwargs.get('phone', '13800138000'),
            email=kwargs.get('email', 'customer@example.com'),
            salesperson=salesperson,
            notes=kwargs.get('notes', ''),
        )

    @staticmethod
    def create_product(name='测试产品', code='TEST001', **kwargs):
        """创建测试产品"""
        from workorder.models.products import Product
        return Product.objects.create(
            name=name,
            code=code,
            specification=kwargs.get('specification', '100x100mm'),
            unit=kwargs.get('unit', '件'),
            unit_price=kwargs.get('unit_price', 10.00),
        )

    @staticmethod
    def create_process(name='测试工序', code='TEST', **kwargs):
        """创建测试工序"""
        from workorder.models.base import Process
        return Process.objects.create(
            name=name,
            code=kwargs.get('code', code),
            is_builtin=kwargs.get('is_builtin', False),
            is_parallel=kwargs.get('is_parallel', False),
            requires_artwork=kwargs.get('requires_artwork', False),
            artwork_required=kwargs.get('artwork_required', False),
        )

    @staticmethod
    def create_workorder(customer=None, creator=None, **kwargs):
        """创建测试施工单"""
        from workorder.models.core import WorkOrder
        from django.utils import timezone
        from datetime import timedelta

        if not customer:
            customer = TestDataFactory.create_customer()

        if not creator:
            creator = TestDataFactory.create_user()

        tomorrow = timezone.now().date() + timedelta(days=1)

        return WorkOrder.objects.create(
            customer=customer,
            production_quantity=kwargs.get('production_quantity', 100),
            order_date=kwargs.get('order_date', timezone.now().date()),
            delivery_date=kwargs.get('delivery_date', tomorrow),
            created_by=creator,
            manager=creator,
            priority=kwargs.get('priority', 'normal'),
            notes=kwargs.get('notes', ''),
        )


class APITestCaseMixin:
    """API 测试混入类 - 提供 API 测试通用方法"""

    def setUp(self):
        """设置认证"""
        super().setUp()
        self.client = self.client_class()
        self.user = TestDataFactory.create_user()
        self.client.force_login(self.user)

    def api_get(self, url, **kwargs):
        """GET 请求"""
        return self.client.get(url, **kwargs)

    def api_post(self, url, data=None, **kwargs):
        """POST 请求"""
        return self.client.post(url, data, content_type='application/json', **kwargs)

    def api_put(self, url, data=None, **kwargs):
        """PUT 请求"""
        return self.client.put(url, data, content_type='application/json', **kwargs)

    def api_patch(self, url, data=None, **kwargs):
        """PATCH 请求"""
        return self.client.patch(url, data, content_type='application/json', **kwargs)

    def api_delete(self, url, **kwargs):
        """DELETE 请求"""
        return self.client.delete(url, **kwargs)

    def assertAPIError(self, response, status_code, message=None):
        """断言 API 错误"""
        self.assertEqual(response.status_code, status_code)
        if message:
            self.assertIn(message, str(response.data))
