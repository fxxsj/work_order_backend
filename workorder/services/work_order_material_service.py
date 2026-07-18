"""施工单物料业务服务"""

from decimal import Decimal, ROUND_CEILING

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework import status

from workorder.constants.status import MaterialPurchaseStatus
from workorder.models.core import WorkOrderMaterial
from workorder.services.service_errors import ServiceError


class WorkOrderMaterialService:
    """施工单物料业务服务"""

    @staticmethod
    def _ceil(value: Decimal) -> Decimal:
        return value.quantize(Decimal("1"), rounding=ROUND_CEILING)

    @staticmethod
    def _inbound_quantity(material) -> Decimal:
        """计算已下单但尚未合格入库的在途数量。"""
        from workorder.models.materials import PurchaseOrderItem

        result = PurchaseOrderItem.objects.filter(
            material=material,
            purchase_order__status="ordered",
        ).aggregate(total=Sum(F("quantity") - F("received_quantity")))["total"]
        return max(Decimal("0"), result or Decimal("0"))

    @staticmethod
    def _unallocated_inbound_quantity(material, *, exclude_wom=None):
        allocated_query = WorkOrderMaterial.objects.filter(
            purchase_material=material,
            planning_status=WorkOrderMaterial.PlanningStatus.CONFIRMED,
        )
        if exclude_wom is not None:
            allocated_query = allocated_query.exclude(pk=exclude_wom.pk)
        allocated = allocated_query.aggregate(total=Sum("inbound_quantity_snapshot"))[
            "total"
        ] or Decimal("0")
        return max(
            Decimal("0"),
            WorkOrderMaterialService._inbound_quantity(material) - allocated,
        )

    @staticmethod
    def _layout_count(parent_width, parent_height, cut_width, cut_height):
        normal = int(parent_width // cut_width) * int(parent_height // cut_height)
        rotated = int(parent_width // cut_height) * int(parent_height // cut_width)
        return max(normal, rotated)

    @staticmethod
    @transaction.atomic
    def calculate_plan(
        *,
        wom: WorkOrderMaterial,
        purchase_material,
        cut_width_mm,
        cut_height_mm,
        required_cut_quantity,
        wastage_rate=Decimal("0"),
        artwork=None,
    ) -> WorkOrderMaterial:
        """由开料尺寸、原纸规格和损耗率计算原纸需求及采购缺口。"""
        wom = WorkOrderMaterial.objects.select_for_update().get(pk=wom.pk)
        if not wom.planning_required:
            raise ServiceError(
                "该施工单物料无需拼版规划",
                code=status.HTTP_400_BAD_REQUEST,
            )
        if wom.material.specification_level != "requirement":
            raise ServiceError(
                "需拼版规划的施工单物料必须使用材料要求层级",
                code=status.HTTP_400_BAD_REQUEST,
            )
        if wom.planning_status == WorkOrderMaterial.PlanningStatus.CONFIRMED:
            raise ServiceError(
                "已确认的物料计划不能直接重算，请先作废原计划",
                code=status.HTTP_409_CONFLICT,
            )
        if purchase_material.specification_level != "stock":
            raise ServiceError(
                "采购规格必须选择库存/采购规格物料",
                code=status.HTTP_400_BAD_REQUEST,
            )
        if not purchase_material.is_active:
            raise ServiceError(
                "所选采购规格已停用",
                code=status.HTTP_400_BAD_REQUEST,
            )
        if (
            wom.material.specification_level == "requirement"
            and purchase_material.base_material_id != wom.material_id
        ):
            raise ServiceError(
                "所选采购规格不属于当前材料要求",
                code=status.HTTP_400_BAD_REQUEST,
            )
        if (
            artwork is not None
            and not wom.work_order.artworks.filter(pk=artwork.pk).exists()
        ):
            raise ServiceError(
                "所选图稿不属于当前施工单",
                code=status.HTTP_400_BAD_REQUEST,
            )

        values = {
            "开料宽度": Decimal(str(cut_width_mm)),
            "开料高度": Decimal(str(cut_height_mm)),
            "所需开料数量": Decimal(str(required_cut_quantity)),
            "损耗率": Decimal(str(wastage_rate or 0)),
        }
        for label, value in values.items():
            if value < 0 or (label != "损耗率" and value <= 0):
                raise ServiceError(
                    f"{label}必须大于0",
                    code=status.HTTP_400_BAD_REQUEST,
                )
        if values["损耗率"] > Decimal("100"):
            raise ServiceError(
                "损耗率不能大于100%",
                code=status.HTTP_400_BAD_REQUEST,
            )

        parent_width = purchase_material.sheet_width_mm
        parent_height = purchase_material.sheet_height_mm
        if not parent_width or not parent_height:
            raise ServiceError(
                "所选采购物料未配置原纸宽度和高度",
                code=status.HTTP_400_BAD_REQUEST,
            )

        pieces = WorkOrderMaterialService._layout_count(
            Decimal(parent_width),
            Decimal(parent_height),
            values["开料宽度"],
            values["开料高度"],
        )
        if pieces <= 0:
            raise ServiceError(
                "开料尺寸大于所选原纸规格，无法排版",
                code=status.HTTP_400_BAD_REQUEST,
            )

        theoretical = WorkOrderMaterialService._ceil(
            values["所需开料数量"] / Decimal(pieces)
        )
        planned = WorkOrderMaterialService._ceil(
            theoretical * (Decimal("1") + values["损耗率"] / Decimal("100"))
        )
        inbound = WorkOrderMaterialService._unallocated_inbound_quantity(
            purchase_material, exclude_wom=wom
        )
        available = Decimal(str(purchase_material.available_quantity))
        shortage = max(Decimal("0"), planned - available - inbound)

        wom.purchase_material = purchase_material
        wom.artwork = artwork
        wom.cut_width_mm = values["开料宽度"]
        wom.cut_height_mm = values["开料高度"]
        wom.parent_sheet_width_mm = parent_width
        wom.parent_sheet_height_mm = parent_height
        wom.required_cut_quantity = values["所需开料数量"]
        wom.pieces_per_parent_sheet = pieces
        wom.theoretical_parent_quantity = theoretical
        wom.wastage_rate = values["损耗率"]
        wom.planned_parent_quantity = planned
        wom.inbound_quantity_snapshot = inbound
        wom.purchase_quantity = shortage
        wom.planning_status = WorkOrderMaterial.PlanningStatus.CALCULATED
        wom.material_size = f"{values['开料宽度']:g}×{values['开料高度']:g}mm"
        wom.material_usage = f"{planned:g}{purchase_material.unit}"
        wom.save()
        return wom

    @staticmethod
    @transaction.atomic
    def confirm_plan(*, wom: WorkOrderMaterial, user) -> WorkOrderMaterial:
        """确认计划并原子预留当前可用库存。"""
        from workorder.models.materials import Material

        purchase_material_id = WorkOrderMaterial.objects.values_list(
            "purchase_material_id", flat=True
        ).get(pk=wom.pk)
        material = Material.objects.select_for_update().get(pk=purchase_material_id)
        wom = WorkOrderMaterial.objects.select_for_update().get(pk=wom.pk)
        if wom.planning_status != WorkOrderMaterial.PlanningStatus.CALCULATED:
            raise ServiceError(
                "只有已计算的物料计划可以确认",
                code=status.HTTP_400_BAD_REQUEST,
            )
        if wom.purchase_material_id != material.pk:
            raise ServiceError(
                "物料计划已发生变化，请重新确认",
                code=status.HTTP_409_CONFLICT,
            )
        inbound_available = WorkOrderMaterialService._unallocated_inbound_quantity(
            material, exclude_wom=wom
        )
        available = Decimal(str(material.available_quantity))
        reserve = min(wom.planned_parent_quantity, available)
        inbound = min(
            wom.planned_parent_quantity - reserve,
            inbound_available,
        )
        purchase_quantity = max(
            Decimal("0"),
            wom.planned_parent_quantity - reserve - inbound,
        )

        material.reserved_quantity = (
            material.reserved_quantity or Decimal("0")
        ) + reserve
        material.save(update_fields=["reserved_quantity"])

        wom.reserved_quantity = reserve
        wom.inbound_quantity_snapshot = inbound
        wom.purchase_quantity = purchase_quantity
        wom.planning_status = WorkOrderMaterial.PlanningStatus.CONFIRMED
        wom.plan_confirmed_by = user
        wom.plan_confirmed_at = timezone.now()
        if reserve >= wom.planned_parent_quantity:
            wom.purchase_status = MaterialPurchaseStatus.RECEIVED
            wom.received_date = timezone.now().date()
        elif inbound > 0 and purchase_quantity == 0:
            wom.purchase_status = MaterialPurchaseStatus.ORDERED
        wom.save(
            update_fields=[
                "reserved_quantity",
                "inbound_quantity_snapshot",
                "purchase_quantity",
                "planning_status",
                "plan_confirmed_by",
                "plan_confirmed_at",
                "purchase_status",
                "received_date",
            ]
        )
        return wom

    @staticmethod
    @transaction.atomic
    def allocate_received_inventory(*, material, quantity, preferred_wom=None) -> None:
        """把合格入库转为施工单库存预留，避免在途承诺落空。"""
        material = material.__class__.objects.select_for_update().get(pk=material.pk)
        remaining = Decimal(str(quantity or 0))
        if remaining <= 0:
            return

        plans = list(
            WorkOrderMaterial.objects.select_for_update()
            .filter(
                purchase_material=material,
                planning_status=WorkOrderMaterial.PlanningStatus.CONFIRMED,
            )
            .order_by("plan_confirmed_at", "pk")
        )
        if preferred_wom is not None:
            plans.sort(key=lambda plan: plan.pk != preferred_wom.pk)

        reserved_total = Decimal("0")
        for plan in plans:
            if remaining <= 0:
                break
            unmet = max(
                Decimal("0"),
                plan.planned_parent_quantity
                - plan.reserved_quantity
                - plan.inbound_quantity_snapshot,
            )
            if preferred_wom is not None and plan.pk == preferred_wom.pk:
                allocation = min(remaining, unmet)
            else:
                allocation = min(
                    remaining,
                    plan.inbound_quantity_snapshot,
                )
                plan.inbound_quantity_snapshot -= allocation
            if allocation <= 0:
                continue
            plan.reserved_quantity += allocation
            if plan.reserved_quantity >= plan.planned_parent_quantity:
                plan.purchase_status = MaterialPurchaseStatus.RECEIVED
                plan.received_date = timezone.now().date()
            plan.save(
                update_fields=[
                    "reserved_quantity",
                    "inbound_quantity_snapshot",
                    "purchase_status",
                    "received_date",
                ]
            )
            remaining -= allocation
            reserved_total += allocation

        if reserved_total > 0:
            material.reserved_quantity += reserved_total
            material.save(update_fields=["reserved_quantity"])

    @staticmethod
    @transaction.atomic
    def invalidate_plan(
        *, wom: WorkOrderMaterial, user, reason: str
    ) -> WorkOrderMaterial:
        """作废计划并释放尚未消耗的库存预留。"""
        from workorder.models.materials import Material, PurchaseOrderItem

        purchase_material_id = WorkOrderMaterial.objects.values_list(
            "purchase_material_id", flat=True
        ).get(pk=wom.pk)
        material = Material.objects.select_for_update().get(pk=purchase_material_id)
        wom = WorkOrderMaterial.objects.select_for_update().get(pk=wom.pk)
        if wom.planning_status != WorkOrderMaterial.PlanningStatus.CONFIRMED:
            raise ServiceError(
                "只有已确认的物料计划可以作废",
                code=status.HTTP_400_BAD_REQUEST,
            )
        if (
            PurchaseOrderItem.objects.filter(
                work_order_material=wom,
            )
            .exclude(purchase_order__status="cancelled")
            .exists()
        ):
            raise ServiceError(
                "物料计划已有未取消的采购单，不能作废",
                code=status.HTTP_409_CONFLICT,
            )
        if wom.purchase_material_id != material.pk:
            raise ServiceError(
                "物料计划已发生变化，请重新操作",
                code=status.HTTP_409_CONFLICT,
            )
        material.reserved_quantity = max(
            Decimal("0"),
            (material.reserved_quantity or Decimal("0")) - wom.reserved_quantity,
        )
        material.save(update_fields=["reserved_quantity"])

        wom.reserved_quantity = Decimal("0")
        wom.inbound_quantity_snapshot = Decimal("0")
        wom.purchase_status = MaterialPurchaseStatus.PENDING
        wom.received_date = None
        wom.planning_status = WorkOrderMaterial.PlanningStatus.INVALIDATED
        wom.plan_version += 1
        log = f"物料计划作废 by {user.username}: {reason or '未填写原因'}"
        wom.notes = f"{wom.notes}\n{log}".strip()
        wom.save(
            update_fields=[
                "reserved_quantity",
                "inbound_quantity_snapshot",
                "purchase_status",
                "received_date",
                "planning_status",
                "plan_version",
                "notes",
            ]
        )
        return wom

    @staticmethod
    def confirm_cutting(
        *,
        wom: WorkOrderMaterial,
        user,
        cut_quantity=None,
        wastage_quantity=None,
        notes: str = "",
    ) -> WorkOrderMaterial:
        """确认物料开料完成。

        将物料状态从 'received' 转换为 'cut'，触发信号自动完成相关开料任务。
        """
        if wom.purchase_status != MaterialPurchaseStatus.RECEIVED:
            raise ServiceError(
                f"物料当前状态为 '{wom.get_purchase_status_display()}'，"
                f"只有 '已回料' 状态可以确认开料",
                code=status.HTTP_400_BAD_REQUEST,
            )

        wom.purchase_status = MaterialPurchaseStatus.CUT
        wom.cut_date = timezone.now().date()
        wom.cut_by = user
        update_fields = ["purchase_status", "cut_date", "cut_by"]

        if cut_quantity is not None:
            wom.cut_quantity = cut_quantity
            update_fields.append("cut_quantity")

        if wastage_quantity is not None:
            wom.wastage_quantity = wastage_quantity
            update_fields.append("wastage_quantity")

        log_parts = [f"确认开料 by {user.username}"]
        if cut_quantity is not None:
            log_parts.append(f"实际开料数量: {cut_quantity}")
        if wastage_quantity is not None:
            log_parts.append(f"损耗数量: {wastage_quantity}")
        if notes:
            log_parts.append(f"备注: {notes}")

        existing = wom.notes or ""
        log_line = " | ".join(log_parts)
        wom.notes = f"{existing}\n{log_line}" if existing else log_line
        update_fields.append("notes")

        wom.save(update_fields=update_fields)
        return wom
