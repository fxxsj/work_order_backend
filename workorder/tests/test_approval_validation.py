"""
审核前验证功能测试
测试施工单在提交审核前的数据完整性验证
"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from ..models import (
    WorkOrder, WorkOrderProcess, WorkOrderProduct, WorkOrderMaterial,
    Customer, Product, Process, Artwork, Die, FoilingPlate, EmbossingPlate,
    Material
)
from datetime import datetime, timedelta


class ApprovalValidationBaseTest(TestCase):
    """审核前验证测试基类"""
    
    def setUp(self):
        """公共测试数据"""
        # 创建用户
        self.salesperson = User.objects.create_user(
            username='salesperson',
            password='testpass123',
            email='sales@example.com'
        )
        
        self.creator = User.objects.create_user(
            username='creator',
            password='testpass123',
            email='creator@example.com'
        )
        
        # 创建客户
        self.customer = Customer.objects.create(
            name='测试客户',
            contact_person='张三',
            phone='13800138000',
            salesperson=self.salesperson
        )
        
        # 创建产品
        self.product = Product.objects.create(
            name='测试产品',
            code='TEST001',
            specification='100x100mm',
            unit='件',
            unit_price=10.00
        )
        
        # 创建工序
        self.process_ctp = Process.objects.create(
            name='CTP制版',
            code='CTP',
            requires_artwork=True,
            artwork_required=True
        )
        
        self.process_prt = Process.objects.create(
            name='印刷',
            code='PRT',
            requires_artwork=True,
            artwork_required=True
        )
        
        self.process_cut = Process.objects.create(
            name='开料',
            code='CUT',
            is_parallel=False
        )
        
        # 创建版
        self.artwork = Artwork.objects.create(
            base_code='ART202401001',
            version=1,
            name='测试图稿',
            confirmed=False
        )
        
        # 创建物料
        self.material = Material.objects.create(
            name='纸张',
            code='PAPER001',
            need_cutting=True
        )


class BasicValidationTest(ApprovalValidationBaseTest):
    """基础信息验证测试"""
    
    def test_customer_required(self):
        """测试客户信息必须"""
        work_order = WorkOrder(
            production_quantity=100,
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('缺少客户信息', errors)
        self.assertGreater(len(errors), 0)
    
    def test_products_required(self):
        """测试产品信息必须"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加工序但不添加产品
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('缺少产品信息', errors)
    
    def test_processes_required(self):
        """测试工序信息必须"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品但不添加工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('缺少工序信息', errors)
    
    def test_delivery_date_required(self):
        """测试交货日期必须"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            delivery_date=None,  # 交货日期为空
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('缺少交货日期', errors)


class PlateProcessMatchTest(ApprovalValidationBaseTest):
    """版与工序匹配验证测试"""
    
    def test_artwork_required_when_process_requires_artwork(self):
        """测试需要图稿的工序必须有图稿"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,  # 需要图稿
            sequence=10
        )
        
        # 不添加图稿
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('需要图稿', errors[0])
        self.assertIn('请至少选择一个图稿', errors[0])
    
    def test_artwork_not_required_when_process_not_require_artwork(self):
        """测试不需要图稿的工序可以没有图稿"""
        # 创建不需要图稿的工序
        process_no_artwork = Process.objects.create(
            name='不需要图稿的工序',
            code='NO_ART',
            requires_artwork=False
        )
        
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=process_no_artwork,
            sequence=10
        )
        
        # 不添加图稿
        
        errors = work_order.validate_before_approval()
        
        # 不应该报图稿相关的错误
        artwork_errors = [e for e in errors if '图稿' in e]
        self.assertEqual(len(artwork_errors), 0)


class QuantityValidationTest(ApprovalValidationBaseTest):
    """数量验证测试"""
    
    def test_production_quantity_required(self):
        """测试生产数量必须填写"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=None,  # 未填写
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('缺少生产数量', errors)
    
    def test_production_quantity_must_be_positive(self):
        """测试生产数量必须大于0"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=-10,  # 小于0
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('生产数量必须大于0', errors[0])
        self.assertIn('-10', errors[0])
    
    def test_production_quantity_zero_is_invalid(self):
        """测试生产数量等于0时无效"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=0,  # 等于0
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('生产数量必须大于0', errors[0])
    
    def test_product_quantity_sum_must_be_positive(self):
        """测试产品数量总和必须大于0"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品但数量为0
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=0  # 数量为0
        )
        
        work_order.artworks.add(self.artwork)
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('产品数量总和必须大于0', errors[0])
        self.assertIn('0', errors[0])


class DateValidationTest(ApprovalValidationBaseTest):
    """日期验证测试"""
    
    def test_delivery_date_before_order_date(self):
        """测试交货日期不能早于下单日期"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            order_date='2026-01-10',
            delivery_date='2026-01-05',  # 交货日期早于下单日期
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('交货日期不能早于下单日期', errors[0])
        self.assertIn('2026-01-05', errors[0])
        self.assertIn('2026-01-10', errors[0])
    
    def test_delivery_date_same_as_order_date(self):
        """测试交货日期可以等于下单日期"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            order_date='2026-01-10',
            delivery_date='2026-01-10',  # 相同日期
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        errors = work_order.validate_before_approval()
        
        # 不应该有日期错误
        date_errors = [e for e in errors if '交货日期' in e]
        self.assertEqual(len(date_errors), 0)
    
    def test_delivery_date_after_order_date(self):
        """测试交货日期可以晚于下单日期"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            order_date='2026-01-10',
            delivery_date='2026-01-20',  # 晚于下单日期
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        errors = work_order.validate_before_approval()
        
        # 不应该有日期错误
        date_errors = [e for e in errors if '交货日期' in e]
        self.assertEqual(len(date_errors), 0)
    
    def test_delivery_date_before_today(self):
        """测试交货日期不能早于今天"""
        yesterday = timezone.now().date() - timedelta(days=1)
        
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            order_date=yesterday,
            delivery_date=yesterday,  # 早于今天
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        errors = work_order.validate_before_approval()
        
        # 应该有"不能早于今天"的错误
        self.assertTrue(any('不能早于今天' in e for e in errors))


class MaterialValidationTest(ApprovalValidationBaseTest):
    """物料验证测试"""
    
    def test_material_usage_required_for_cutting_material(self):
        """测试需要开料的物料必须填写用量"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        # 添加物料但未填写用量
        WorkOrderMaterial.objects.create(
            work_order=work_order,
            material=self.material,
            need_cutting=True,  # 需要开料
            material_usage=""  # 未填写用量
        )
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('需要开料', errors[0])
        self.assertIn('请填写物料用量', errors[0])
    
    def test_material_usage_not_required_for_non_cutting_material(self):
        """测试不需要开料的物料可以不填写用量"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        # 添加不需要开料的物料
        material_no_cutting = Material.objects.create(
            name='不需要开料的物料',
            code='NO_CUT001',
            need_cutting=False
        )
        
        WorkOrderMaterial.objects.create(
            work_order=work_order,
            material=material_no_cutting,
            need_cutting=False,  # 不需要开料
            material_usage=""  # 未填写用量
        )
        
        errors = work_order.validate_before_approval()
        
        # 不应该有物料用量相关的错误
        material_errors = [e for e in errors if '物料用量' in e]
        self.assertEqual(len(material_errors), 0)


class ProcessSequenceValidationTest(ApprovalValidationBaseTest):
    """工序顺序验证测试"""
    
    def test_ctp_before_prt(self):
        """测试制版应该在印刷之前"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        # 制版在后（错误）
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=20
        )
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_prt,
            sequence=10  # 印刷在前
        )
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('制版工序（CTP）应该在印刷工序（PRT）之前', errors[0])
        self.assertIn('请调整工序顺序', errors[0])
    
    def test_ctp_after_prt(self):
        """测试制版在印刷之后时正确"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        # 制版在前（正确）
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10  # 制版在前
        )
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_prt,
            sequence=20  # 印刷在后
        )
        
        errors = work_order.validate_before_approval()
        
        # 不应该有顺序错误
        sequence_errors = [e for e in errors if '应该在' in e]
        self.assertEqual(len(sequence_errors), 0)
    
    def test_cut_before_prt(self):
        """测试开料应该在印刷之前"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        # 开料在后（错误）
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_cut,
            sequence=20
        )
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_prt,
            sequence=10  # 印刷在前
        )
        
        errors = work_order.validate_before_approval()
        
        self.assertIn('开料工序（CUT）应该在印刷工序（PRT）之前', errors[0])
        self.assertIn('请调整工序顺序', errors[0])
    
    def test_cut_after_prt(self):
        """测试开料在印刷之后时正确"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            delivery_date='2026-01-20',
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        # 开料在前（正确）
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_prt,
            sequence=10  # 印刷在前
        )
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_cut,
            sequence=20  # 开料在后
        )
        
        errors = work_order.validate_before_approval()
        
        # 不应该有顺序错误
        sequence_errors = [e for e in errors if '应该在' in e]
        self.assertEqual(len(sequence_errors), 0)


class IntegrationTest(ApprovalValidationBaseTest):
    """集成测试"""
    
    def test_valid_work_order_passes_all_validations(self):
        """测试数据完整的施工单可以通过所有验证"""
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=100,
            order_date=today,
            delivery_date=tomorrow,
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品和工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        work_order.artworks.add(self.artwork)
        
        # 制版在前，印刷在后
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_ctp,
            sequence=10
        )
        
        WorkOrderProcess.objects.create(
            work_order=work_order,
            process=self.process_prt,
            sequence=20
        )
        
        # 添加不需要开料的物料
        material_no_cutting = Material.objects.create(
            name='测试物料',
            code='TEST_MAT001',
            need_cutting=False
        )
        
        WorkOrderMaterial.objects.create(
            work_order=work_order,
            material=material_no_cutting,
            need_cutting=False
        )
        
        errors = work_order.validate_before_approval()
        
        # 不应该有任何错误
        self.assertEqual(len(errors), 0)
    
    def test_multiple_errors_returned(self):
        """测试多个错误时返回所有错误"""
        work_order = WorkOrder(
            customer=self.customer,
            production_quantity=-10,  # 错误1：数量小于0
            delivery_date=None,  # 错误2：缺少交货日期
            created_by=self.creator,
            manager=self.creator
        )
        work_order.save()
        
        # 添加产品但不添加工序
        WorkOrderProduct.objects.create(
            work_order=work_order,
            product=self.product,
            quantity=50
        )
        
        errors = work_order.validate_before_approval()
        
        # 应该有多个错误
        self.assertGreater(len(errors), 1)
        self.assertTrue(any('生产数量' in e for e in errors))
        self.assertTrue(any('交货日期' in e for e in errors))
        self.assertTrue(any('工序' in e for e in errors))

