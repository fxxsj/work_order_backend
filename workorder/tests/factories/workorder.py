"""Factory Boy definitions for work order models"""
import factory
from datetime import date, timedelta
from django.utils import timezone
from .base import DepartmentFactory, ProcessFactory
from .users import UserFactory
from workorder.models.core import (
    WorkOrder, WorkOrderProcess, WorkOrderTask, WorkOrderProduct
)
from workorder.models.base import Customer
from workorder.models.products import Product


class CustomerFactory(factory.django.DjangoModelFactory):
    """Factory for Customer model"""

    class Meta:
        model = Customer

    name = factory.Sequence(lambda n: f"Customer {n}")
    contact_person = factory.Faker('name', locale='zh_CN')
    phone = factory.Faker('phone_number', locale='zh_CN')
    email = factory.Sequence(lambda n: f"contact{n}@example.com")


class ProductFactory(factory.django.DjangoModelFactory):
    """Factory for Product model"""

    class Meta:
        model = Product

    name = factory.Sequence(lambda n: f"Product {n}")
    code = factory.Sequence(lambda n: f"PROD{n:04d}")
    specification = "100x100mm"
    unit = "件"
    unit_price = 10.00
    product_type = "single"
    is_active = True


class WorkOrderFactory(factory.django.DjangoModelFactory):
    """Factory for WorkOrder model"""

    class Meta:
        model = WorkOrder

    order_number = factory.Sequence(lambda n: f"WO{n:06d}")
    customer = factory.SubFactory(CustomerFactory)
    created_by = factory.SubFactory(UserFactory)
    manager = factory.SubFactory(UserFactory)
    production_quantity = 100
    order_date = factory.LazyFunction(lambda: date.today())
    delivery_date = factory.LazyFunction(lambda: date.today() + timedelta(days=7))
    priority = 'normal'
    approval_status = 'pending'
    status = 'pending'

    # Post-generation: create processes
    @factory.post_generation
    def processes(obj, create, extracted, **kwargs):
        """Create work order processes after creation"""
        if not create:
            return

        if extracted is None:
            # Create default process if none specified
            WorkOrderProcessFactory(work_order=obj)
        elif isinstance(extracted, int):
            # Create N processes
            WorkOrderProcessFactory.create_batch(extracted, work_order=obj)
        elif isinstance(extracted, list):
            # Use provided list of process data
            for process_data in extracted:
                WorkOrderProcessFactory(work_order=obj, **process_data)


class WorkOrderProcessFactory(factory.django.DjangoModelFactory):
    """Factory for WorkOrderProcess model"""

    class Meta:
        model = WorkOrderProcess

    work_order = factory.SubFactory(WorkOrderFactory)
    process = factory.SubFactory(ProcessFactory)
    sequence = 10
    status = 'pending'

    # Post-generation: create tasks
    @factory.post_generation
    def tasks(obj, create, extracted, **kwargs):
        """Create tasks after process creation"""
        if not create:
            return

        if extracted is None:
            # Create one task by default
            extracted = 1

        if isinstance(extracted, int) and extracted > 0:
            for _ in range(extracted):
                task = WorkOrderTaskFactory(
                    work_order_process=obj,
                    status='draft'
                )
                # work_order and process are derived from work_order_process
                # Don't pass them explicitly


class WorkOrderProductFactory(factory.django.DjangoModelFactory):
    """Factory for WorkOrderProduct model"""

    class Meta:
        model = WorkOrderProduct

    work_order = factory.SubFactory(WorkOrderFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = 100


class WorkOrderTaskFactory(factory.django.DjangoModelFactory):
    """Factory for WorkOrderTask model"""

    class Meta:
        model = WorkOrderTask

    work_order_process = factory.SubFactory(WorkOrderProcessFactory)
    work_content = 'Complete task'
    status = 'draft'
    task_type = 'general'
    production_quantity = 100
    quantity_completed = 0
    quantity_defective = 0
    auto_calculate_quantity = True
    version = 1

    # Conditional assignment using parameters (use **kwargs to pass these)
    assigned_department = None
    assigned_operator = None
