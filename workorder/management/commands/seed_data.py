from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict
import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from workorder.models import (
    ApprovalEscalation,
    ApprovalRule,
    ApprovalStep,
    ApprovalWorkflow,
    Artwork,
    ArtworkProduct,
    AuditLog,
    AuditLogExport,
    AuditLogSettings,
    CostCenter,
    CostItem,
    Customer,
    DeliveryItem,
    DeliveryOrder,
    Department,
    Die,
    DieProduct,
    EmbossingPlate,
    EmbossingPlateProduct,
    FoilingPlate,
    FoilingPlateProduct,
    Invoice,
    Material,
    MaterialSupplier,
    Notification,
    Payment,
    PaymentPlan,
    Process,
    ProcessLog,
    Product,
    ProductGroup,
    ProductGroupItem,
    ProductMaterial,
    ProductStock,
    ProductStockLog,
    ProductionCost,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceiveRecord,
    QualityInspection,
    SalesOrder,
    SalesOrderItem,
    Statement,
    StockIn,
    StockOut,
    Supplier,
    TaskAssignmentRule,
    TaskLog,
    UserProfile,
    WorkOrder,
    WorkOrderApprovalLog,
    WorkOrderMaterial,
    WorkOrderProcess,
    WorkOrderProduct,
    WorkOrderTask,
)


@dataclass
class Sequence:
    counters: Dict[str, int] = field(default_factory=dict)

    def next(self, prefix: str, width: int = 4) -> str:
        value = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = value
        return f"{prefix}{value:0{width}d}"


class Command(BaseCommand):
    help = "填充测试数据（覆盖 workorder 业务表）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scale",
            type=int,
            default=1,
            help="数据规模倍数（默认 1，所有核心实体会按倍数创建）",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=0,
            help="随机种子（保留参数，当前实现不使用）",
        )

    def handle(self, *args, **options):
        scale = max(1, int(options["scale"]))
        seq = Sequence()
        tag = uuid.uuid4().hex[:6]
        User = get_user_model()

        with transaction.atomic():
            # === 用户与部门 ===
            dept_prod = self._get_or_create_department("生产部", "production")
            dept_design = self._get_or_create_department("设计部", "design")

            process_print = self._get_or_create_process("印刷", "print")
            process_pack = self._get_or_create_process("包装", "pack")
            process_cut = self._get_or_create_process("开料", "cut")

            dept_prod.processes.add(process_print, process_pack, process_cut)
            dept_design.processes.add(process_print)

            admin = self._get_or_create_user(User, "admin_seed", is_staff=True, is_superuser=True)
            salesperson = self._get_or_create_user(User, "sales_seed", is_staff=True)
            manager = self._get_or_create_user(User, "manager_seed", is_staff=True)
            operator = self._get_or_create_user(User, "operator_seed", is_staff=True)
            approver = self._get_or_create_user(User, "approver_seed", is_staff=True)

            self._ensure_profile(admin, [dept_prod])
            self._ensure_profile(salesperson, [dept_prod])
            self._ensure_profile(manager, [dept_design])
            self._ensure_profile(operator, [dept_prod])
            self._ensure_profile(approver, [dept_prod])

            # === 客户 ===
            customers = []
            for _ in range(scale * 3):
                customer = Customer.objects.create(
                    name=f"客户_{seq.next('CUST')}",
                    contact_person="联系人",
                    phone="13800138000",
                    salesperson=salesperson,
                )
                customers.append(customer)

            # === 供应商 & 物料 ===
            supplier, _ = Supplier.objects.get_or_create(
                code=f"sup_{tag}",
                defaults={
                    "name": f"供应商_{seq.next('SUP')}",
                    "contact_person": "供应联系人",
                    "phone": "021-55556666",
                },
            )
            material, _ = Material.objects.get_or_create(
                code=f"mat_{tag}".upper(),
                defaults={
                    "name": f"物料_{seq.next('MAT')}",
                    "unit_price": Decimal("12.50"),
                    "default_supplier": supplier,
                    "need_cutting": True,
                },
            )
            MaterialSupplier.objects.get_or_create(
                material=material,
                supplier=supplier,
                defaults={
                    "supplier_price": Decimal("12.50"),
                    "is_preferred": True,
                },
            )

            # === 产品 ===
            product_group, _ = ProductGroup.objects.get_or_create(
                code=f"PG{tag}".upper(),
                defaults={
                    "name": f"产品组_{seq.next('PG')}",
                },
            )
            product, _ = Product.objects.get_or_create(
                code=f"PRD{tag}".upper(),
                defaults={
                    "name": f"产品_{seq.next('PROD')}",
                    "unit_price": Decimal("98.00"),
                    "product_group": product_group,
                    "product_type": "single",
                },
            )
            product.default_processes.add(process_print, process_pack)

            product_item, _ = Product.objects.get_or_create(
                code=f"PRD{tag}I".upper(),
                defaults={
                    "name": f"产品子项_{seq.next('PROD')}",
                    "unit_price": Decimal("50.00"),
                    "product_group": product_group,
                    "product_type": "group_item",
                },
            )
            ProductGroupItem.objects.get_or_create(
                product_group=product_group,
                product=product_item,
                defaults={
                    "item_name": "子项",
                },
            )
            ProductMaterial.objects.get_or_create(
                product=product,
                material=material,
                defaults={
                    "material_usage": "100张",
                    "need_cutting": True,
                },
            )
            ProductStockLog.objects.create(
                product=product,
                change_type="add",
                quantity=10,
                old_quantity=0,
                new_quantity=10,
                reason="初始化库存",
                created_by=manager,
            )

            # === 资产 ===
            die = Die.objects.create(
                code=f"DIE{tag}".upper(),
                name="刀模示例",
                die_type="dedicated",
            )
            foiling = FoilingPlate.objects.create(
                code=f"FP{tag}".upper(),
                name="烫金版示例",
            )
            embossing = EmbossingPlate.objects.create(
                code=f"EP{tag}".upper(),
                name="压凸版示例",
            )
            artwork = Artwork.objects.create(
                base_code=f"ART{tag}".upper(),
                version=1,
                name="图稿示例",
                confirmed_by=manager,
            )
            artwork.dies.add(die)
            artwork.foiling_plates.add(foiling)
            artwork.embossing_plates.add(embossing)
            ArtworkProduct.objects.create(artwork=artwork, product=product)
            DieProduct.objects.create(die=die, product=product)
            FoilingPlateProduct.objects.create(foiling_plate=foiling, product=product)
            EmbossingPlateProduct.objects.create(embossing_plate=embossing, product=product)

            # === 销售订单 ===
            sales_order = SalesOrder.objects.create(
                order_number=SalesOrder.generate_order_number(),
                customer=customers[0],
                status="approved",
                order_date=date.today(),
                delivery_date=date.today() + timedelta(days=10),
                total_amount=Decimal("9800.00"),
                created_by=salesperson,
            )
            sales_item = SalesOrderItem.objects.create(
                sales_order=sales_order,
                product=product,
                quantity=100,
                unit_price=Decimal("98.00"),
            )

            # === 施工单 ===
            work_order = WorkOrder.objects.create(
                order_number=f"WOSEED{timezone.now().strftime('%Y%m%d')}{tag.upper()}",
                customer=customers[0],
                order_date=date.today(),
                delivery_date=date.today() + timedelta(days=7),
                production_quantity=100,
                total_amount=Decimal("9800.00"),
                manager=manager,
                created_by=manager,
                status="pending",
                approval_status="pending",
            )
            WorkOrderProduct.objects.create(
                work_order=work_order,
                product=product,
                quantity=100,
                sort_order=0,
            )
            work_order_process = WorkOrderProcess.objects.create(
                work_order=work_order,
                process=process_print,
                department=dept_prod,
                sequence=1,
            )
            work_order_material = WorkOrderMaterial.objects.create(
                work_order=work_order,
                material=material,
                material_usage="100张",
                need_cutting=True,
            )
            task = WorkOrderTask.objects.create(
                work_order_process=work_order_process,
                task_type="printing",
                work_content="测试印刷任务",
                production_quantity=100,
                product=product,
                assigned_department=dept_prod,
                assigned_operator=operator,
                status="pending",
            )
            ProcessLog.objects.create(
                work_order_process=work_order_process,
                log_type="start",
                content="开始工序",
                operator=operator,
            )
            TaskLog.objects.create(
                task=task,
                log_type="status_change",
                content="任务创建",
                operator=operator,
                status_before="draft",
                status_after="pending",
            )

            # === 系统 ===
            WorkOrderApprovalLog.objects.create(
                work_order=work_order,
                approval_status=work_order.approval_status,
                approved_by=approver,
                approval_comment="初始化审核记录",
            )
            Notification.objects.create(
                recipient=manager,
                notification_type="system",
                title="测试通知",
                content="这是测试通知",
                priority="normal",
                work_order=work_order,
                work_order_process=work_order_process,
                task=task,
            )
            TaskAssignmentRule.objects.get_or_create(
                process=process_print,
                department=dept_prod,
                defaults={
                    "priority": 100,
                    "operator_selection_strategy": "least_tasks",
                },
            )

            # === 多级审核 ===
            workflow = ApprovalWorkflow.objects.create(
                name="默认流程",
                workflow_type="simple",
                steps={"steps": ["主管审核"]},
                created_by=manager,
            )
            approval_step = ApprovalStep.objects.create(
                work_order=work_order,
                workflow=workflow,
                step_name="主管审核",
                step_order=1,
                assigned_to=approver,
                status="pending",
            )
            ApprovalRule.objects.create(
                name="默认规则",
                rule_type="value_based",
                workflow_type="simple",
                conditions={"min_amount": 0},
                created_by=manager,
            )
            ApprovalEscalation.objects.create(
                work_order=work_order,
                from_step=approval_step,
                to_step=None,
                escalation_reason="测试上报",
                status="pending",
                escalated_by=approver,
            )

            # === 采购 ===
            purchase_order = PurchaseOrder.objects.create(
                order_number=PurchaseOrder.generate_order_number(),
                supplier=supplier,
                status="submitted",
                total_amount=Decimal("1250.00"),
                submitted_by=manager,
                work_order=work_order,
            )
            purchase_item = PurchaseOrderItem.objects.create(
                purchase_order=purchase_order,
                material=material,
                quantity=Decimal("100"),
                unit_price=Decimal("12.50"),
            )
            PurchaseReceiveRecord.objects.create(
                purchase_order_item=purchase_item,
                received_quantity=Decimal("100"),
                received_by=manager,
                inspected_by=manager,
                inspection_status="qualified",
                qualified_quantity=Decimal("100"),
                is_stocked=True,
                stocked_by=manager,
            )

            # === 库存 ===
            product_stock = ProductStock.objects.create(
                product=product,
                quantity=Decimal("100"),
                unit_cost=Decimal("80.00"),
                batch_no=f"BATCH{tag}".upper(),
                work_order=work_order,
            )
            stock_in = StockIn.objects.create(
                work_order=work_order,
                status="completed",
                operator=operator,
            )
            stock_out = StockOut.objects.create(
                out_type="delivery",
                status="completed",
                operator=operator,
            )
            delivery_order = DeliveryOrder.objects.create(
                sales_order=sales_order,
                customer=customers[0],
                receiver_name="收货人",
                receiver_phone="13800138000",
                delivery_address="测试地址",
                created_by=manager,
            )
            DeliveryItem.objects.create(
                delivery_order=delivery_order,
                product=product,
                sales_order_item=sales_item,
                quantity=Decimal("10"),
                unit_price=Decimal("98.00"),
            )
            QualityInspection.objects.create(
                inspection_type="final",
                work_order=work_order,
                product=product,
                inspector=operator,
                result="passed",
            )

            # === 财务 ===
            cost_center = CostCenter.objects.create(
                name="生产成本中心",
                code=f"CC{tag}".upper(),
                type="production",
                manager=manager,
            )
            cost_item = CostItem.objects.create(
                name="材料费",
                code=f"CI{tag}".upper(),
                type="material",
                allocation_method="direct",
            )
            ProductionCost.objects.create(
                work_order=work_order,
                period=timezone.now().strftime("%Y-%m"),
                material_cost=Decimal("500.00"),
                labor_cost=Decimal("200.00"),
                overhead_cost=Decimal("100.00"),
                total_cost=Decimal("800.00"),
            )
            invoice = Invoice.objects.create(
                customer=customers[0],
                sales_order=sales_order,
                work_order=work_order,
                amount=Decimal("9800.00"),
                tax_rate=Decimal("13.00"),
                created_by=manager,
            )
            payment = Payment.objects.create(
                customer=customers[0],
                sales_order=sales_order,
                invoice=invoice,
                amount=Decimal("1000.00"),
                payment_method="transfer",
                recorded_by=manager,
            )
            PaymentPlan.objects.create(
                sales_order=sales_order,
                plan_amount=Decimal("9800.00"),
                plan_date=date.today() + timedelta(days=30),
            )
            Statement.objects.create(
                statement_type="customer",
                customer=customers[0],
                period=timezone.now().strftime("%Y-%m"),
                start_date=date.today().replace(day=1),
                end_date=date.today(),
                created_by=manager,
            )

            # === 审计日志 ===
            AuditLogSettings.get_settings()
            content_type = ContentType.objects.get_for_model(WorkOrder)
            AuditLog.objects.create(
                action_type=AuditLog.ACTION_CREATE,
                user=manager,
                content_type=content_type,
                object_id=str(work_order.id),
                object_repr=work_order.order_number,
                changes={"created": True},
                changed_fields=["order_number"],
                ip_address="127.0.0.1",
                request_method="POST",
                request_path="/api/v1/workorders/",
            )
            AuditLogExport.objects.create(
                user=manager,
                start_date=timezone.now() - timedelta(days=7),
                end_date=timezone.now(),
                filters={},
                status=AuditLogExport.STATUS_COMPLETED,
                file_path="exports/audit_seed.csv",
                record_count=1,
                file_size=128,
                completed_at=timezone.now(),
            )

        self.stdout.write(self.style.SUCCESS("已完成测试数据填充（workorder 全部业务表）。"))

    def _get_or_create_user(self, User, username, is_staff=False, is_superuser=False):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "is_staff": is_staff,
                "is_superuser": is_superuser,
                "email": f"{username}@example.com",
            },
        )
        if created:
            user.set_password("123456")
            user.save(update_fields=["password"])
        return user

    def _ensure_profile(self, user, departments):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if departments:
            profile.departments.add(*departments)
        return profile

    def _get_or_create_department(self, name, code):
        dept, _ = Department.objects.get_or_create(name=name, defaults={"code": code})
        if dept.code != code:
            dept.code = code
            dept.save(update_fields=["code"])
        return dept

    def _get_or_create_process(self, name, code):
        process, _ = Process.objects.get_or_create(name=name, defaults={"code": code})
        if process.code != code:
            process.code = code
            process.save(update_fields=["code"])
        return process
