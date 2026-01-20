"""
产品 API 测试

测试产品、产品物料、产品组相关的 API 功能。
"""

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse

from workorder.models.products import Product, ProductMaterial, ProductGroup, ProductGroupItem
from workorder.models import Material, Process


class ProductSerializerTest(TestCase):
    """产品序列化器测试"""

    def setUp(self):
        """测试前准备"""
        self.process = Process.objects.create(
            name='印刷',
            code='print',
            department_id=1
        )

    def test_validate_code_valid(self):
        """测试有效的产品编码"""
        from workorder.serializers.products import ProductSerializer

        valid_codes = ['PROD-001', 'ABC123', 'product-123', '12345']
        for code in valid_codes:
            serializer = ProductSerializer(data={'code': code, 'name': '测试产品'})
            self.assertTrue(serializer.is_valid(), f'编码 {code} 应该是有效的')

    def test_validate_code_invalid(self):
        """测试无效的产品编码"""
        from workorder.serializers.products import ProductSerializer

        invalid_codes = ['PROD_001', '产品@123', 'PROD.001', 'PROD 001', '', 'A']
        for code in invalid_codes:
            serializer = ProductSerializer(data={'code': code, 'name': '测试产品'})
            self.assertFalse(serializer.is_valid(), f'编码 {code} 应该是无效的')

    def test_validate_unit_price_negative(self):
        """测试单价不能为负数"""
        from workorder.serializers.products import ProductSerializer

        serializer = ProductSerializer(data={
            'code': 'PROD-001',
            'name': '测试产品',
            'unit_price': -10
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('unit_price', serializer.errors)

    def test_validate_unit_price_exceeds_limit(self):
        """测试单价超出范围"""
        from workorder.serializers.products import ProductSerializer

        serializer = ProductSerializer(data={
            'code': 'PROD-001',
            'name': '测试产品',
            'unit_price': 999999999.99
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('unit_price', serializer.errors)

    def test_validate_stock_quantity_negative(self):
        """测试库存数量不能为负数"""
        from workorder.serializers.products import ProductSerializer

        serializer = ProductSerializer(data={
            'code': 'PROD-001',
            'name': '测试产品',
            'stock_quantity': -10
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('stock_quantity', serializer.errors)

    def test_validate_min_stock_greater_than_stock(self):
        """测试最小库存不能大于库存数量（编辑时）"""
        from workorder.serializers.products import ProductSerializer

        # 创建一个产品
        product = Product.objects.create(
            code='PROD-001',
            name='测试产品',
            stock_quantity=100,
            min_stock_quantity=10
        )

        # 尝试将最小库存设置为大于库存数量
        serializer = ProductSerializer(
            product,
            data={
                'code': 'PROD-001',
                'name': '测试产品',
                'stock_quantity': 50,
                'min_stock_quantity': 100
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('min_stock_quantity', serializer.errors)


class ProductAPITest(APITestCase):
    """产品 API 测试"""

    def setUp(self):
        """测试前准备"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@test.com'
        )

        # 创建测试数据
        self.product_data = {
            'code': 'PROD-001',
            'name': '测试产品',
            'specification': 'A4规格',
            'unit': '件',
            'unit_price': 10.50,
            'stock_quantity': 100,
            'min_stock_quantity': 10,
            'description': '测试产品描述',
            'is_active': True
        }

    def test_create_product_as_admin(self):
        """测试管理员创建产品"""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            '/api/products/',
            self.product_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Product.objects.get().code, 'PROD-001')

    def test_create_product_with_invalid_code(self):
        """测试创建产品时使用无效编码"""
        self.client.force_authenticate(user=self.admin_user)

        invalid_data = self.product_data.copy()
        invalid_data['code'] = 'PROD_001'  # 包含下划线

        response = self.client.post(
            '/api/products/',
            invalid_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_product_with_negative_price(self):
        """测试创建产品时使用负单价"""
        self.client.force_authenticate(user=self.admin_user)

        invalid_data = self.product_data.copy()
        invalid_data['unit_price'] = -10

        response = self.client.post(
            '/api/products/',
            invalid_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_product(self):
        """测试更新产品"""
        self.client.force_authenticate(user=self.admin_user)

        # 创建产品
        product = Product.objects.create(**self.product_data)

        # 更新产品
        update_data = {
            'name': '更新后的产品名称',
            'unit_price': 15.00
        }

        response = self.client.patch(
            f'/api/products/{product.id}/',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        product.refresh_from_db()
        self.assertEqual(product.name, '更新后的产品名称')
        self.assertEqual(float(product.unit_price), 15.00)

    def test_delete_product(self):
        """测试删除产品"""
        self.client.force_authenticate(user=self.admin_user)

        # 创建产品
        product = Product.objects.create(**self.product_data)

        # 删除产品
        response = self.client.delete(f'/api/products/{product.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Product.objects.count(), 0)

    def test_list_products(self):
        """测试获取产品列表"""
        self.client.force_authenticate(user=self.user)

        # 创建多个产品
        Product.objects.create(code='PROD-001', name='产品1')
        Product.objects.create(code='PROD-002', name='产品2')

        response = self.client.get('/api/products/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_search_products(self):
        """测试搜索产品"""
        self.client.force_authenticate(user=self.user)

        # 创建产品
        Product.objects.create(code='PROD-001', name='印刷产品A')
        Product.objects.create(code='PROD-002', name='包装产品B')

        # 搜索
        response = self.client.get('/api/products/?search=印刷')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], '印刷产品A')

    def test_filter_products_by_active(self):
        """测试按启用状态过滤产品"""
        self.client.force_authenticate(user=self.user)

        # 创建产品
        Product.objects.create(code='PROD-001', name='产品1', is_active=True)
        Product.objects.create(code='PROD-002', name='产品2', is_active=False)

        # 过滤启用产品
        response = self.client.get('/api/products/?is_active=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class ProductStockTest(TestCase):
    """产品库存操作测试"""

    def setUp(self):
        """测试前准备"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.product = Product.objects.create(
            code='PROD-001',
            name='测试产品',
            stock_quantity=100,
            min_stock_quantity=10
        )

    def test_add_stock(self):
        """测试增加库存"""
        result = self.product.add_stock(50, user=self.user, reason='入库')

        self.assertTrue(result)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 150)

        # 检查日志
        from workorder.models.products import ProductStockLog
        log = ProductStockLog.objects.filter(product=self.product).last()
        self.assertEqual(log.quantity, 50)
        self.assertEqual(log.change_type, 'add')

    def test_add_stock_invalid_quantity(self):
        """测试增加库存时数量无效"""
        result = self.product.add_stock(0)
        self.assertFalse(result)

        result = self.product.add_stock(-10)
        self.assertFalse(result)

    def test_reduce_stock(self):
        """测试减少库存"""
        result = self.product.reduce_stock(30, user=self.user, reason='出库')

        self.assertTrue(result)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 70)

        # 检查日志
        from workorder.models.products import ProductStockLog
        log = ProductStockLog.objects.filter(product=self.product).last()
        self.assertEqual(log.quantity, -30)
        self.assertEqual(log.change_type, 'reduce')

    def test_reduce_stock_insufficient(self):
        """测试减少库存时库存不足"""
        with self.assertRaises(ValueError) as context:
            self.product.reduce_stock(150)

        self.assertIn('库存不足', str(context.exception))

    def test_stock_low_warning(self):
        """测试库存预警"""
        # 减少库存到预警值以下
        self.product.reduce_stock(95, user=self.user, reason='测试')

        self.product.refresh_from_db()
        self.assertTrue(self.product.is_low_stock())


class ProductMaterialAPITest(APITestCase):
    """产品物料 API 测试"""

    def setUp(self):
        """测试前准备"""
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='admin123'
        )

        self.material = Material.objects.create(
            name='铜版纸',
            code='MAT-001',
            unit='张'
        )

        self.product = Product.objects.create(
            code='PROD-001',
            name='测试产品'
        )

    def test_create_product_material(self):
        """测试创建产品物料"""
        self.client.force_authenticate(user=self.admin_user)

        data = {
            'product': self.product.id,
            'material': self.material.id,
            'material_size': 'A4',
            'material_usage': '1000张',
            'need_cutting': True,
            'notes': '测试备注'
        }

        response = self.client.post(
            '/api/product-materials/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProductMaterial.objects.count(), 1)

    def test_list_product_materials(self):
        """测试获取产品物料列表"""
        self.client.force_authenticate(user=self.admin_user)

        # 创建产品物料
        ProductMaterial.objects.create(
            product=self.product,
            material=self.material
        )

        response = self.client.get(f'/api/product-materials/?product={self.product.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
