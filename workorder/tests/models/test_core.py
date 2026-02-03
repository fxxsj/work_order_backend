"""
核心视图单元测试
测试 WorkOrder, WorkOrderTask, WorkOrderProcess API 视图
"""
import pytest
from workorder.models.core import WorkOrder, WorkOrderTask, WorkOrderProcess
from workorder.tests.conftest import TestDataFactory
from workorder.serializers.core import WorkOrderListSerializer, WorkOrderCreateUpdateSerializer


@pytest.mark.django_db
class TestWorkOrderModel:
    """WorkOrder 模型测试"""

    def test_order_number_generation(self):
        """测试施工单号自动生成"""
        work_order = TestDataFactory.create_workorder()
        
        assert work_order.order_number is not None
        assert len(work_order.order_number) >= 8

    def test_order_number_uniqueness(self):
        """测试施工单号唯一性"""
        import uuid
        work_order1 = TestDataFactory.create_workorder(username=f'user1_{uuid.uuid4().hex[:8]}')
        work_order2 = TestDataFactory.create_workorder(username=f'user2_{uuid.uuid4().hex[:8]}')
        
        assert work_order1.order_number != work_order2.order_number

    def test_default_status(self):
        """测试默认状态值"""
        work_order = TestDataFactory.create_workorder()
        
        assert work_order.status == 'pending'
        assert work_order.approval_status == 'pending'

    def test_default_priority(self):
        """测试默认优先级"""
        work_order = TestDataFactory.create_workorder()
        
        assert work_order.priority == 'normal'

    def test_progress_percentage_calculation(self):
        """测试进度百分比计算"""
        work_order = TestDataFactory.create_workorder()
        
        progress = work_order.get_progress_percentage()
        assert progress == 0

    def test_progress_with_completed_processes(self):
        """测试有完成工序时的进度计算"""
        work_order = TestDataFactory.create_workorder()
        process = TestDataFactory.create_workorder_process(
            work_order=work_order,
            status='completed'
        )
        
        progress = work_order.get_progress_percentage()
        assert 0 <= progress <= 100

    def test_str_representation(self):
        """测试字符串表示"""
        work_order = TestDataFactory.create_workorder()
        
        str_repr = str(work_order)
        assert work_order.order_number in str_repr


@pytest.mark.django_db
class TestWorkOrderTaskModel:
    """WorkOrderTask 模型测试"""

    def test_default_status(self):
        """测试默认任务状态"""
        work_order = TestDataFactory.create_workorder()
        process = TestDataFactory.create_workorder_process(work_order=work_order)
        
        task = WorkOrderTask.objects.create(
            work_order_process=process,
            task_type='general',
            work_content='测试任务',
            production_quantity=100
        )
        
        assert task.status == 'pending'

    def test_status_transition(self):
        """测试状态转换"""
        work_order = TestDataFactory.create_workorder()
        process = TestDataFactory.create_workorder_process(work_order=work_order)
        
        task = WorkOrderTask.objects.create(
            work_order_process=process,
            task_type='general',
            work_content='测试任务',
            production_quantity=100,
            status='pending'
        )
        
        task.status = 'in_progress'
        task.save()
        
        assert task.status == 'in_progress'

    def test_status_transition_to_completed(self):
        """测试状态转换：进行中 -> 已完成"""
        work_order = TestDataFactory.create_workorder()
        process = TestDataFactory.create_workorder_process(work_order=work_order)
        
        task = WorkOrderTask.objects.create(
            work_order_process=process,
            task_type='general',
            work_content='测试任务',
            production_quantity=100,
            status='in_progress'
        )
        
        task.status = 'completed'
        task.save()
        
        assert task.status == 'completed'

    def test_task_assignment(self):
        """测试任务分派"""
        import uuid
        work_order = TestDataFactory.create_workorder(username=f'wo_{uuid.uuid4().hex[:8]}')
        process = TestDataFactory.create_workorder_process(work_order=work_order)
        department = TestDataFactory.create_department(name=f'印刷部_{uuid.uuid4().hex[:4]}')
        
        task = WorkOrderTask.objects.create(
            work_order_process=process,
            task_type='general',
            work_content='测试任务',
            production_quantity=100,
            assigned_department=department
        )
        
        assert task.assigned_department == department
        assert task.status == 'pending'

    def test_str_representation(self):
        """测试字符串表示"""
        work_order = TestDataFactory.create_workorder()
        process = TestDataFactory.create_workorder_process(work_order=work_order)
        
        task = WorkOrderTask.objects.create(
            work_order_process=process,
            task_type='general',
            work_content='测试任务内容',
            production_quantity=100
        )
        
        str_repr = str(task)
        assert '测试任务内容' in str_repr


@pytest.mark.django_db
class TestWorkOrderProcessModel:
    """WorkOrderProcess 模型测试"""

    def test_default_status(self):
        """测试默认工序状态"""
        work_order = TestDataFactory.create_workorder()
        process = TestDataFactory.create_process()
        
        wo_process = WorkOrderProcess.objects.create(
            work_order=work_order,
            process=process,
            sequence=1
        )
        
        assert wo_process.status == 'pending'

    def test_can_start_sequential_process(self):
        """测试串行工序的开始条件"""
        work_order = TestDataFactory.create_workorder()
        
        process1 = TestDataFactory.create_process(code='P1')
        wo_process1 = WorkOrderProcess.objects.create(
            work_order=work_order,
            process=process1,
            sequence=1,
            status='completed'
        )
        
        process2 = TestDataFactory.create_process(code='P2', is_parallel=False)
        wo_process2 = WorkOrderProcess.objects.create(
            work_order=work_order,
            process=process2,
            sequence=2,
            status='pending'
        )
        
        assert wo_process2.can_start() == True

    def test_can_start_parallel_process(self):
        """测试并行工序的开始条件"""
        work_order = TestDataFactory.create_workorder()
        
        process = TestDataFactory.create_process(code='PAR', is_parallel=True)
        wo_process = WorkOrderProcess.objects.create(
            work_order=work_order,
            process=process,
            sequence=1,
            status='pending'
        )
        
        assert wo_process.can_start() == True

    def test_status_transition(self):
        """测试工序状态转换"""
        work_order = TestDataFactory.create_workorder()
        process = TestDataFactory.create_process()
        
        wo_process = WorkOrderProcess.objects.create(
            work_order=work_order,
            process=process,
            sequence=1,
            status='pending'
        )
        
        wo_process.status = 'in_progress'
        wo_process.save()
        
        assert wo_process.status == 'in_progress'

    def test_str_representation(self):
        """测试字符串表示"""
        work_order = TestDataFactory.create_workorder()
        process = TestDataFactory.create_process(name='印刷工序')
        
        wo_process = WorkOrderProcess.objects.create(
            work_order=work_order,
            process=process,
            sequence=1
        )
        
        str_repr = str(wo_process)
        assert '印刷工序' in str_repr


@pytest.mark.django_db
class TestWorkOrderSerializer:
    """WorkOrder 序列化器测试"""

    def test_valid_serializer(self):
        """测试有效数据的序列化"""
        customer = TestDataFactory.create_customer()
        work_order = TestDataFactory.create_workorder(customer=customer)

        serializer = WorkOrderListSerializer(work_order)
        data = serializer.data

        assert data['id'] == work_order.id
        assert data['order_number'] == work_order.order_number
        assert data['status'] == work_order.status

    def test_deserialize_create(self):
        """测试反序列化创建数据"""
        customer = TestDataFactory.create_customer()

        # 提供必填字段products_data
        data = {
            'customer': customer.id,
            'production_quantity': 200,
            'delivery_date': '2026-02-15',
            'priority': 'high',
            'products_data': [],
            'processes': [],
        }

        serializer = WorkOrderCreateUpdateSerializer(data=data)
        # 验证数据有效
        assert serializer.is_valid(), f"Errors: {serializer.errors}"
