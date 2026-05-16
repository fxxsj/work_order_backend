"""Factory Boy definitions for material models"""
import factory
from workorder.models.materials import Material, Supplier, MaterialSupplier, PurchaseOrder, PurchaseOrderItem, PurchaseReceiveRecord
from workorder.models.core import WorkOrderMaterial


class SupplierFactory(factory.django.DjangoModelFactory):
    """Factory for Supplier model"""

    class Meta:
        model = Supplier

    name = factory.Sequence(lambda n: f"Supplier {n}")
    code = factory.Sequence(lambda n: f"SUP{n:04d}")
    contact_person = factory.Faker("name", locale="zh_CN")
    phone = factory.Faker("phone_number", locale="zh_CN")
    email = factory.Sequence(lambda n: f"supplier{n}@example.com")
    status = "active"


class MaterialFactory(factory.django.DjangoModelFactory):
    """Factory for Material model"""

    class Meta:
        model = Material

    name = factory.Sequence(lambda n: f"Material {n}")
    code = factory.Sequence(lambda n: f"MAT{n:04d}")
    specification = "100x100mm"
    unit = "张"
    unit_price = 5.00
    stock_quantity = 0
    min_stock_quantity = 10
    default_supplier = factory.SubFactory(SupplierFactory)
    lead_time_days = 7
    need_cutting = False


class MaterialSupplierFactory(factory.django.DjangoModelFactory):
    """Factory for MaterialSupplier model"""

    class Meta:
        model = MaterialSupplier

    material = factory.SubFactory(MaterialFactory)
    supplier = factory.SubFactory(SupplierFactory)
    supplier_price = 4.50
    is_preferred = True
    min_order_quantity = 1


class WorkOrderMaterialFactory(factory.django.DjangoModelFactory):
    """Factory for WorkOrderMaterial model"""

    class Meta:
        model = WorkOrderMaterial

    work_order = factory.SubFactory("workorder.tests.factories.workorder.WorkOrderFactory")
    material = factory.SubFactory(MaterialFactory)
    material_size = "A4"
    material_usage = factory.Sequence(lambda n: f"{n * 100}张")
    need_cutting = False
    purchase_status = "pending"


class PurchaseOrderFactory(factory.django.DjangoModelFactory):
    """Factory for PurchaseOrder model"""

    class Meta:
        model = PurchaseOrder

    supplier = factory.SubFactory(SupplierFactory)
    status = "draft"
    total_amount = 0


class PurchaseOrderItemFactory(factory.django.DjangoModelFactory):
    """Factory for PurchaseOrderItem model"""

    class Meta:
        model = PurchaseOrderItem

    purchase_order = factory.SubFactory(PurchaseOrderFactory)
    material = factory.SubFactory(MaterialFactory)
    quantity = 100
    unit_price = 5.00
    status = "pending"


class PurchaseReceiveRecordFactory(factory.django.DjangoModelFactory):
    """Factory for PurchaseReceiveRecord model"""

    class Meta:
        model = PurchaseReceiveRecord

    purchase_order_item = factory.SubFactory(PurchaseOrderItemFactory)
    received_quantity = 100
    inspection_status = "pending"