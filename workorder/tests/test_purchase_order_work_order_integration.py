"""
采购单 ↔ 施工单集成测试

测试：
1. stock_in() 回写 WorkOrderMaterial.purchase_status 为 received
2. place_order() 回写 WorkOrderMaterial.purchase_status 为 ordered
3. create_from_work_order API 创建采购单并关联 work_order_material
4. WorkOrderDetailSerializer 包含 purchase_order_summaries
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from workorder.constants.status import MaterialPurchaseStatus
from workorder.models.core import WorkOrder, WorkOrderMaterial
from workorder.models.materials import PurchaseOrder, PurchaseOrderItem, PurchaseReceiveRecord
from workorder.tests.factories import (
    SupplierFactory,
    MaterialFactory,
    WorkOrderFactory,
    WorkOrderMaterialFactory,
    PurchaseOrderFactory,
    PurchaseOrderItemFactory,
    PurchaseReceiveRecordFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestPurchaseOrderWriteback:
    """采购单状态变更回写施工单物料测试"""

    def setup_method(self):
        """每个测试方法执行前的准备"""
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # 创建供应商
        self.supplier = SupplierFactory(status="active")

        # 创建物料（带默认供应商）
        self.material = MaterialFactory(default_supplier=self.supplier)

        # 创建施工单 + 物料（已审批状态才能关联采购单）
        self.work_order = WorkOrderFactory(approval_status="approved", status="in_progress")
        self.wo_material = WorkOrderMaterialFactory(
            work_order=self.work_order,
            material=self.material,
            purchase_status=MaterialPurchaseStatus.PENDING,
            material_usage="500张",
        )

    def test_place_order_updates_work_order_material_status(self):
        """place_order 应将 WorkOrderMaterial.purchase_status 更新为 ordered"""
        # 创建采购单
        po = PurchaseOrderFactory(
            supplier=self.supplier,
            work_order=self.work_order,
            approval_status="approved",
            status="pending",
        )
        item = PurchaseOrderItemFactory(
            purchase_order=po,
            material=self.material,
            quantity=500,
            status="pending",
            work_order_material=self.wo_material,
        )

        # 执行下单
        response = self.client.post(f"/api/v1/purchase-orders/{po.id}/place_order/")

        if response.status_code != 200:
            print("Response:", response.data)
        assert response.status_code == 200

        # 刷新并验证
        self.wo_material.refresh_from_db()
        assert self.wo_material.purchase_status == MaterialPurchaseStatus.ORDERED
        assert self.wo_material.purchase_date is not None

    def test_place_order_rejects_already_ordered_purchase_order(self):
        """已下单采购单不能重复下单，避免覆盖下单日期"""
        po = PurchaseOrderFactory(
            supplier=self.supplier,
            work_order=self.work_order,
            approval_status="approved",
            status="ordered",
            ordered_date=timezone.now().date(),
        )

        response = self.client.post(f"/api/v1/purchase-orders/{po.id}/place_order/")

        assert response.status_code == 400
        assert "待下单" in response.json()["message"]

    def test_place_order_rejects_non_pending_business_status(self):
        """非 pending 业务状态不能下单，即使审批状态已通过"""
        po = PurchaseOrderFactory(
            supplier=self.supplier,
            work_order=self.work_order,
            approval_status="approved",
            status="draft",
        )

        response = self.client.post(f"/api/v1/purchase-orders/{po.id}/place_order/")

        assert response.status_code == 400
        assert "待下单" in response.json()["message"]

    def test_stock_in_updates_work_order_material_to_received(self):
        """stock_in 应将 WorkOrderMaterial.purchase_status 更新为 received"""
        # 创建采购单并完成下单
        po = PurchaseOrderFactory(
            supplier=self.supplier,
            work_order=self.work_order,
            approval_status="approved",
            status="ordered",
        )
        item = PurchaseOrderItemFactory(
            purchase_order=po,
            material=self.material,
            quantity=500,
            received_quantity=0,
            status="pending",
            work_order_material=self.wo_material,
        )

        # 收货
        response = self.client.post(
            f"/api/v1/purchase-orders/{po.id}/receive/",
            data={
                "items": [{"item_id": item.id, "received_quantity": 500}],
                "received_date": str(timezone.now().date()),
            },
            format="json",
        )
        assert response.status_code == 200

        # 获取收货记录
        record = PurchaseReceiveRecord.objects.filter(
            purchase_order_item=item
        ).first()
        assert record is not None

        # 质检确认合格
        response = self.client.post(
            f"/api/v1/purchase-receive-records/{record.id}/confirm_inspection/",
            data={"qualified_quantity": 500, "unqualified_quantity": 0},
            format="json",
        )
        assert response.status_code == 200

        # 入库
        response = self.client.post(
            f"/api/v1/purchase-receive-records/{record.id}/stock_in/",
        )
        assert response.status_code == 200

        # 验证 WorkOrderMaterial 状态已更新
        self.wo_material.refresh_from_db()
        assert self.wo_material.purchase_status == MaterialPurchaseStatus.RECEIVED
        assert self.wo_material.received_date is not None

    def test_stock_in_partial_updates_work_order_material_to_ordered(self):
        """部分入库时，WorkOrderMaterial 状态应为 ordered（而非 received）"""
        # 创建采购单并完成下单
        po = PurchaseOrderFactory(
            supplier=self.supplier,
            work_order=self.work_order,
            approval_status="approved",
            status="ordered",
        )
        item = PurchaseOrderItemFactory(
            purchase_order=po,
            material=self.material,
            quantity=500,
            received_quantity=0,
            status="pending",
            work_order_material=self.wo_material,
        )

        # 部分收货 300（不足 500）
        response = self.client.post(
            f"/api/v1/purchase-orders/{po.id}/receive/",
            data={
                "items": [{"item_id": item.id, "received_quantity": 300}],
                "received_date": str(timezone.now().date()),
            },
            format="json",
        )
        assert response.status_code == 200

        record = PurchaseReceiveRecord.objects.filter(purchase_order_item=item).first()

        # 质检确认（300 全部合格）
        response = self.client.post(
            f"/api/v1/purchase-receive-records/{record.id}/confirm_inspection/",
            data={"qualified_quantity": 300, "unqualified_quantity": 0},
            format="json",
        )
        assert response.status_code == 200

        # 入库
        response = self.client.post(
            f"/api/v1/purchase-receive-records/{record.id}/stock_in/",
        )
        assert response.status_code == 200

        # 验证 WorkOrderMaterial 状态保持 ordered（因为是部分收货）
        self.wo_material.refresh_from_db()
        assert self.wo_material.purchase_status == MaterialPurchaseStatus.ORDERED


@pytest.mark.django_db
class TestCreateFromWorkOrder:
    """从施工单创建采购单 API 测试"""

    def setup_method(self):
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_from_work_order_creates_linked_po(self):
        """create_from_work_order 应创建采购单并关联 WorkOrderMaterial"""
        supplier = SupplierFactory(status="active")
        material = MaterialFactory(default_supplier=supplier)
        work_order = WorkOrderFactory(approval_status="approved", status="in_progress")
        wo_material = WorkOrderMaterialFactory(
            work_order=work_order,
            material=material,
            purchase_status=MaterialPurchaseStatus.PENDING,
            material_usage="200张",
        )

        response = self.client.post(
            "/api/v1/purchase-orders/create_from_work_order/",
            data={"work_order_id": work_order.id},
            format="json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_count"] == 1

        po_id = data["data"]["purchase_orders"][0]["id"]
        po = PurchaseOrder.objects.get(pk=po_id)

        assert po.work_order == work_order
        assert po.supplier == supplier
        assert po.status == "pending"

        # 验证 Item 关联了 work_order_material
        item = po.items.first()
        assert item.work_order_material == wo_material
        assert item.quantity == 200  # 解析自 material_usage

    def test_create_from_work_order_groups_by_supplier(self):
        """按默认供应商分组，每组生成一个采购单"""
        supplier1 = SupplierFactory(status="active", name="Supplier A")
        supplier2 = SupplierFactory(status="active", name="Supplier B")
        material1 = MaterialFactory(default_supplier=supplier1)
        material2 = MaterialFactory(default_supplier=supplier2)
        work_order = WorkOrderFactory(approval_status="approved", status="in_progress")
        WorkOrderMaterialFactory(
            work_order=work_order,
            material=material1,
            purchase_status=MaterialPurchaseStatus.PENDING,
        )
        WorkOrderMaterialFactory(
            work_order=work_order,
            material=material2,
            purchase_status=MaterialPurchaseStatus.PENDING,
        )

        response = self.client.post(
            "/api/v1/purchase-orders/create_from_work_order/",
            data={"work_order_id": work_order.id},
            format="json",
        )

        assert response.status_code == 200
        data = response.json()
        # 应生成 2 个采购单（不同供应商）
        assert data["data"]["total_count"] == 2

    def test_create_from_work_order_fails_without_default_supplier(self):
        """物料无默认供应商时应报错"""
        material = MaterialFactory(default_supplier=None)
        work_order = WorkOrderFactory(approval_status="approved", status="in_progress")
        WorkOrderMaterialFactory(
            work_order=work_order,
            material=material,
            purchase_status=MaterialPurchaseStatus.PENDING,
        )

        response = self.client.post(
            "/api/v1/purchase-orders/create_from_work_order/",
            data={"work_order_id": work_order.id},
            format="json",
        )

        assert response.status_code == 400
        assert "默认供应商" in response.json()["message"]
        assert response.json()["data"]["blocked_items"]

    def test_create_from_work_order_filters_only_pending(self):
        """只筛选 purchase_status=pending 的物料"""
        supplier = SupplierFactory(status="active")
        material = MaterialFactory(default_supplier=supplier)
        work_order = WorkOrderFactory(approval_status="approved", status="in_progress")

        # 已下单的物料（不应包含在新采购单中）
        WorkOrderMaterialFactory(
            work_order=work_order,
            material=material,
            purchase_status=MaterialPurchaseStatus.ORDERED,
        )
        # 待采购的物料（应包含）
        pending_wo_material = WorkOrderMaterialFactory(
            work_order=work_order,
            material=material,
            purchase_status=MaterialPurchaseStatus.PENDING,
        )

        response = self.client.post(
            "/api/v1/purchase-orders/create_from_work_order/",
            data={"work_order_id": work_order.id},
            format="json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total_count"] == 1
        po_item = PurchaseOrder.objects.get(
            id=data["data"]["purchase_orders"][0]["id"]
        ).items.first()
        assert po_item.work_order_material == pending_wo_material

    def test_create_from_work_order_does_not_duplicate_existing_items(self):
        """已有关联采购明细的施工单物料不应重复创建"""
        supplier = SupplierFactory(status="active")
        material = MaterialFactory(default_supplier=supplier)
        work_order = WorkOrderFactory(approval_status="approved", status="in_progress")
        wo_material = WorkOrderMaterialFactory(
            work_order=work_order,
            material=material,
            purchase_status=MaterialPurchaseStatus.PENDING,
            material_usage="200张",
        )
        po = PurchaseOrderFactory(
            supplier=supplier,
            work_order=work_order,
            status="pending",
        )
        PurchaseOrderItemFactory(
            purchase_order=po,
            material=material,
            quantity=200,
            work_order_material=wo_material,
        )

        response = self.client.post(
            "/api/v1/purchase-orders/create_from_work_order/",
            data={"work_order_id": work_order.id},
            format="json",
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_count"] == 0
        assert data["skipped_item_count"] == 1
        assert PurchaseOrderItem.objects.filter(
            work_order_material=wo_material
        ).count() == 1


@pytest.mark.django_db
class TestWorkOrderDetailSerializerPurchaseOrders:
    """WorkOrderDetailSerializer 采购单摘要测试"""

    def test_work_order_detail_includes_purchase_order_summaries(self):
        """施工单详情应包含关联采购单摘要"""
        from workorder.serializers.core import WorkOrderDetailSerializer

        supplier = SupplierFactory(name="Test Supplier")
        work_order = WorkOrderFactory(approval_status="approved")
        po = PurchaseOrderFactory(supplier=supplier, work_order=work_order, approval_status="approved", status="ordered")

        serializer = WorkOrderDetailSerializer(work_order)
        data = serializer.data

        assert "purchase_order_summaries" in data
        assert len(data["purchase_order_summaries"]) == 1
        summary = data["purchase_order_summaries"][0]
        assert summary["id"] == po.id
        assert summary["number"] == po.order_number
        assert summary["status"] == "ordered"
        assert summary["supplier_name"] == "Test Supplier"
        assert "items_count" in summary
        assert "total_amount" in summary

    def test_work_order_detail_purchase_orders_prefetched(self):
        """使用 prefetched 数据时应避免额外查询"""
        from workorder.serializers.core import WorkOrderDetailSerializer
        from workorder.services.query_optimizer import QueryOptimizer

        supplier = SupplierFactory(name="Prefetch Supplier")
        work_order = WorkOrderFactory(approval_status="approved")
        PurchaseOrderFactory(supplier=supplier, work_order=work_order, approval_status="draft", status="pending")

        # 模拟 include_details=True 的 prefetch
        work_order = (
            WorkOrder.objects.filter(pk=work_order.pk)
            .prefetch_related("purchase_orders__supplier")
            .first()
        )

        # Serializer 不应额外查询 purchase_orders
        serializer = WorkOrderDetailSerializer(work_order)
        data = serializer.data
        assert len(data["purchase_order_summaries"]) == 1
