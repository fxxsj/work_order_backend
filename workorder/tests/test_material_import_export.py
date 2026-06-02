import io
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from openpyxl import Workbook
from workorder.models.materials import Material, Supplier


class MaterialImportExportTest(APITestCase):
    """测试物料导入与导出功能"""

    def setUp(self):
        # 创建超级用户
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password123'
        )
        self.client.force_authenticate(user=self.user)
        
        # 创建一个测试供应商
        self.supplier = Supplier.objects.create(
            name="测试供应商",
            code="SUP00001",
            status="active"
        )
        
        # 创建测试物料
        self.material = Material.objects.create(
            name="测试物料1",
            code="MAT00001",
            specification="100g",
            unit="张",
            unit_price=1.5,
            stock_quantity=100.0,
            min_stock_quantity=10.0,
            default_supplier=self.supplier,
            lead_time_days=5,
            need_cutting=True,
            notes="测试备注"
        )

    def test_export_materials(self):
        """测试导出物料列表 API"""
        url = reverse('material-export')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename='))

    def test_import_materials_success(self):
        """测试导入物料"""
        # 创建一个内存 Excel 文件
        wb = Workbook()
        ws = wb.active
        ws.title = "物料列表"
        
        # 写入表头
        headers = ['编码', '名称', '规格', '单位', '单价', '库存数量', '最小库存', '默认供应商', '采购周期', '是否需要开料', '备注']
        ws.append(headers)
        
        # 写入一条更新数据（MAT00001），和一条新增数据（MAT00002）
        ws.append(['MAT00001', '测试物料1_已更新', '120g', '张', '2.0', '150.0', '15.0', '测试供应商', '8', '否', '已更新备注'])
        ws.append(['MAT00002', '测试物料2', '200g', '个', '5.5', '50.0', '5.0', '测试供应商', '3', '是', '新建物料'])
        
        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)
        excel_file.name = 'materials_import.xlsx'
        
        url = reverse('material-import-materials')
        response = self.client.post(url, {'file': excel_file}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('success_count', response.data['data'])
        self.assertEqual(response.data['data']['created_count'], 1)
        self.assertEqual(response.data['data']['updated_count'], 1)
        self.assertEqual(response.data['data']['error_count'], 0)
        
        # 验证数据库中的值
        mat1 = Material.objects.get(code='MAT00001')
        self.assertEqual(mat1.name, '测试物料1_已更新')
        self.assertEqual(mat1.specification, '120g')
        self.assertEqual(mat1.unit_price, 2.0)
        self.assertEqual(mat1.need_cutting, False)
        
        mat2 = Material.objects.get(code='MAT00002')
        self.assertEqual(mat2.name, '测试物料2')
        self.assertEqual(mat2.specification, '200g')
        self.assertEqual(mat2.need_cutting, True)
        self.assertEqual(mat2.default_supplier, self.supplier)
