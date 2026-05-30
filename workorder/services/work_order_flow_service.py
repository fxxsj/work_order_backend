"""
施工单业务流程编排服务 (WorkOrderFlowService)

负责编排施工单的完整业务流程，包括：
- 从客户订单创建施工单
- 提交审核流程
- 审核通过后的任务分派
- 状态流转与事件触发

设计原则：
1. 事务一致性：使用 @transaction.atomic 确保原子性
2. 状态机约束：严格的状态转换验证
3. 事件驱动：状态变更触发业务事件
4. 可追溯性：完整的操作日志

Author: 小可 AI Assistant
Date: 2026-03-03
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from django.db import transaction
from django.db.models import Sum, F
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework import status

from ..permissions.permission_utils import is_sales_user
from ..models.core import (
    WorkOrder,
    WorkOrderProcess,
    WorkOrderTask,
    WorkOrderProduct,
    WorkOrderMaterial,
    APPROVED_ORDER_EDITABLE_FIELDS,
)
from ..models.sales import SalesOrder, SalesOrderItem
from ..models.inventory import ProductStock
from ..models.system import (
    WorkOrderApprovalLog,
    Notification,
    TaskAssignmentRule,
)
from ..models.base import Customer, Department
from workorder.constants.status import (
    SalesOrderStatus,
    TaskStatus,
    WorkOrderApprovalStatus,
    WorkOrderStatus,
)
from .service_errors import ServiceError
from .work_order_service import WorkOrderService
from .dispatch_service import AutoDispatchService
from .notification_triggers_flow import NotificationTriggers

logger = logging.getLogger(__name__)


class WorkOrderFlowService:
    """
    施工单业务流程编排服务

    作为业务流程的"总指挥"，协调各个服务完成完整的业务流程。
    """

    # ========== 状态转换规则 ==========
    ALLOWED_STATUS_TRANSITIONS = {
        WorkOrderApprovalStatus.DRAFT: [WorkOrderApprovalStatus.SUBMITTED],
        WorkOrderApprovalStatus.SUBMITTED: [WorkOrderApprovalStatus.APPROVED, WorkOrderApprovalStatus.REJECTED],
        WorkOrderApprovalStatus.REJECTED: [WorkOrderApprovalStatus.SUBMITTED],
        WorkOrderApprovalStatus.APPROVED: [WorkOrderApprovalStatus.SUBMITTED],
    }

    @staticmethod
    def _validate_status_transition(current_status: str, new_status: str) -> None:
        """
        验证状态转换是否合法

        Args:
            current_status: 当前状态
            new_status: 目标状态

        Raises:
            ServiceError: 状态转换不合法时抛出
        """
        allowed_transitions = WorkOrderFlowService.ALLOWED_STATUS_TRANSITIONS.get(
            current_status, []
        )
        if new_status not in allowed_transitions:
            raise ServiceError(
                f"不允许的状态转换：{current_status} → {new_status}",
                code=status.HTTP_400_BAD_REQUEST,  # HTTP 400 Bad Request
            )

    @staticmethod
    def _validate_approval_actor(*, work_order: WorkOrder, user: User) -> None:
        """校验施工单审核人，避免视图绕过 service 直接改审核状态。"""
        if user is None or not user.is_authenticated:
            raise ServiceError(
                "请先登录后再审核施工单", code=status.HTTP_401_UNAUTHORIZED
            )

        can_review_by_role = is_sales_user(user)
        can_review_by_perm = user.is_superuser or user.has_perm(
            "workorder.change_workorder"
        )
        if not (can_review_by_role or can_review_by_perm):
            raise ServiceError(
                "只有业务员或主管可以审核施工单", code=status.HTTP_403_FORBIDDEN
            )

        if (
            can_review_by_role
            and not can_review_by_perm
            and work_order.customer.salesperson != user
        ):
            raise ServiceError(
                "只能审核自己负责的施工单", code=status.HTTP_403_FORBIDDEN
            )

    # ========== 流程 1: 从客户订单创建施工单 ==========

    @staticmethod
    @transaction.atomic
    def create_from_sales_order(
        *,
        sales_order_id: int,
        production_quantity: Optional[int],
        selected_items: Optional[List[Dict[str, Any]]] = None,
        delivery_date: Optional[datetime] = None,
        priority: str = "normal",
        notes: str = "",
        created_by: User,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> WorkOrder:
        """
        从客户订单创建施工单（完整流程）

        流程步骤：
        1. 验证客户订单状态
        2. 复制客户、产品信息
        3. 根据产品配置自动生成工序
        4. 根据产品配置自动生成物料清单
        5. 记录操作日志
        6. 发送通知

        Args:
            sales_order_id: 客户订单ID
            production_quantity: 生产数量
            delivery_date: 交货日期
            priority: 优先级
            notes: 备注
            created_by: 创建人
            additional_data: 额外数据（图稿、刀模等）

        Returns:
            WorkOrder: 创建的施工单对象

        Raises:
            ServiceError: 业务逻辑错误
        """
        # 1. 加载并验证客户订单
        try:
            sales_order = SalesOrder.objects.select_related("customer").get(
                id=sales_order_id
            )
        except SalesOrder.DoesNotExist as exc:
            raise ServiceError(
                "客户订单不存在", code=status.HTTP_404_NOT_FOUND
            ) from exc

        if sales_order.status not in [SalesOrderStatus.APPROVED, SalesOrderStatus.IN_PRODUCTION]:
            raise ServiceError(
                f"只有已审核或生产中的客户订单才能创建施工单，当前状态：{sales_order.status}",
                code=status.HTTP_400_BAD_REQUEST,
            )

        production_items = WorkOrderFlowService._build_selected_production_items(
            sales_order,
            selected_items=selected_items,
        )
        if not production_items:
            production_items = WorkOrderFlowService._build_production_items(sales_order)
        if not production_items:
            raise ServiceError(
                "客户订单库存充足，无需生成施工单", code=status.HTTP_400_BAD_REQUEST
            )

        if production_quantity is not None:
            try:
                production_quantity = int(production_quantity)
            except (TypeError, ValueError) as exc:
                raise ServiceError(
                    "生产数量无效", code=status.HTTP_400_BAD_REQUEST
                ) from exc

        if production_quantity is None:
            production_quantity = sum(
                item["produce_quantity"] for item in production_items
            )

        if production_quantity <= 0:
            raise ServiceError(
                "客户订单没有可生产数量", code=status.HTTP_400_BAD_REQUEST
            )

        # 2. 生成施工单号
        order_number = WorkOrderFlowService._generate_order_number()

        # 3. 创建施工单
        work_order = WorkOrder.objects.create(
            order_number=order_number,
            customer=sales_order.customer,
            sales_order=sales_order,
            order_date=sales_order.order_date,
            production_quantity=production_quantity,
            delivery_date=delivery_date or sales_order.delivery_date,
            total_amount=sales_order.total_amount,
            priority=priority,
            notes=notes,
            created_by=created_by,
            status=WorkOrderStatus.PENDING,  # 初始状态
            approval_status=WorkOrderApprovalStatus.DRAFT,  # 草稿，提交后才进入待审核
        )

        logger.info(f"从客户订单 {sales_order.order_number} 创建施工单 {order_number}")

        # 4. 复制客户订单产品
        WorkOrderFlowService._copy_sales_order_products(
            work_order, sales_order, production_items=production_items
        )

        # 5. 根据产品配置自动生成工序
        WorkOrderFlowService._auto_generate_processes(work_order)

        # 6. 根据产品配置自动生成物料
        WorkOrderFlowService._auto_generate_materials(work_order)

        # 7. 关联资产（图稿、刀模等）
        if additional_data:
            WorkOrderFlowService._link_assets(work_order, additional_data)

        # 8. 记录操作日志
        WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            approval_status=work_order.approval_status,
            approved_by=created_by,
            approval_comment=f"从客户订单 {sales_order.order_number} 创建",
        )

        # 9. 发送通知
        NotificationTriggers.notify_workorder_created(
            work_order=work_order,
            recipient=created_by,
        )

        return work_order

    # ========== 流程 2: 提交审核 ==========

    @staticmethod
    @transaction.atomic
    def submit_for_approval(
        *,
        work_order_id: int,
        submitted_by: User,
        comment: str = "",
        auto_approve: bool = False,
    ) -> WorkOrder:
        """
        提交施工单审核

        注意：数据完整性验证已在保存施工单时完成，此处只验证状态转换。

        流程步骤：
        1. 验证施工单状态（必须是草稿或已拒绝）
        2. 状态转换为待审核
        3. 记录提交日志
        4. 发送审核通知给业务员

        Args:
            work_order_id: 施工单ID
            submitted_by: 提交人
            comment: 提交备注

        Returns:
            WorkOrder: 更新后的施工单对象

        Raises:
            ServiceError: 业务逻辑错误
        """
        # 1. 加载施工单
        try:
            work_order = WorkOrder.objects.select_related("customer").get(
                id=work_order_id
            )
        except WorkOrder.DoesNotExist as exc:
            raise ServiceError(
                "施工订单不存在", code=status.HTTP_404_NOT_FOUND
            ) from exc

        # 2. 验证状态
        WorkOrderFlowService._validate_status_transition(
            work_order.approval_status, WorkOrderApprovalStatus.SUBMITTED
        )

        # 3. 状态转换（数据完整性已在保存时验证）
        # 提交审核不删除任务；已投产变更的任务同步由复审通过后的专门流程处理。
        work_order.approval_status = WorkOrderApprovalStatus.SUBMITTED
        work_order.approved_by = None
        work_order.approved_at = None
        work_order.approval_comment = comment
        work_order.save(
            update_fields=[
                "approval_status",
                "approved_by",
                "approved_at",
                "approval_comment",
                "updated_at",
            ]
        )

        logger.info(f"施工单 {work_order.order_number} 提交审核")

        # 6. 记录操作日志
        WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            approval_status=work_order.approval_status,
            approved_by=submitted_by,
            approval_comment=comment or "提交审核",
        )

        # 7. 发送通知给业务员
        salesperson = work_order.customer.salesperson
        if salesperson:
            NotificationTriggers.notify_approval_requested(
                work_order=work_order,
                recipient=salesperson,
                comment=comment,
            )

        if auto_approve:
            can_review_by_role = is_sales_user(submitted_by)
            can_review_by_perm = submitted_by.is_superuser or submitted_by.has_perm("workorder.change_workorder")
            if (can_review_by_role or can_review_by_perm):
                if can_review_by_perm or work_order.customer.salesperson == submitted_by:
                    return WorkOrderFlowService.approve(
                        work_order_id=work_order.id,
                        approved_by=submitted_by,
                        comment="系统自动审核通过（快捷发布）"
                    )

        return work_order

    # ========== 流程 3: 审核通过（自动化流程）==========

    @staticmethod
    @transaction.atomic
    def handle_approval_passed(
        *,
        work_order: WorkOrder,
        approved_by: User,
        comment: str = "",
    ) -> WorkOrder:
        """
        处理审核通过（完整自动化流程）

        流程步骤：
        1. 生成正式任务并自动分派（一次性生成所有工序的任务）
        2. 状态转换：pending → approved → in_progress
        3. 记录审核日志
        4. 发送通知给相关部门和操作员

        注意：任务在审核通过时一次性生成，工序开始时不再重复生成。

        Args:
            work_order: 施工单对象
            approved_by: 审核人
            comment: 审核意见

        Returns:
            WorkOrder: 更新后的施工单对象

        Raises:
            ServiceError: 业务逻辑错误
        """
        work_order.refresh_from_db()
        logger.info(f"开始处理施工单 {work_order.order_number} 的审核通过流程")

        WorkOrderFlowService._validate_approval_actor(
            work_order=work_order,
            user=approved_by,
        )
        WorkOrderFlowService._validate_status_transition(
            work_order.approval_status, WorkOrderApprovalStatus.APPROVED
        )

        # 注意：数据完整性已在保存时验证，无需重复验证

        # 1. 生成正式任务并自动分派
        from workorder.services.task_generation import TaskGenerationService

        task_result = TaskGenerationService.generate_tasks_and_dispatch(work_order)
        logger.info(
            f"施工单 {work_order.order_number} 生成了 {task_result['created_count']} 个任务，"
            f"分派了 {task_result['dispatched_count']} 个"
        )

        # 2. 状态转换
        work_order.approval_status = WorkOrderApprovalStatus.APPROVED
        work_order.approved_by = approved_by
        work_order.approved_at = timezone.now()
        work_order.approval_comment = comment
        work_order.status = WorkOrderStatus.IN_PROGRESS
        work_order.save()

        # 3. 记录审核日志
        WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            approval_status=work_order.approval_status,
            approved_by=approved_by,
            approval_comment=comment,
        )

        # 4. 发送通知
        NotificationTriggers.notify_approval_passed(
            work_order=work_order,
            dispatch_result=task_result,
        )

        logger.info(f"施工单 {work_order.order_number} 审核通过流程完成")
        return work_order

    # ========== 流程 4: 审核拒绝 ==========

    @staticmethod
    @transaction.atomic
    def handle_approval_rejected(
        *,
        work_order: WorkOrder,
        rejected_by: User,
        reason: str,
    ) -> WorkOrder:
        """
        处理审核拒绝（完整流程）

        流程步骤：
        1. 状态转换：pending → rejected
        2. 记录拒绝日志
        3. 发送通知给创建人

        注意：审核拒绝时，已生成的任务保留在数据库中。
        如果施工单重新提交审核并通过，之前的任务会被删除并重新生成。

        Args:
            work_order: 施工单对象
            rejected_by: 审核人
            reason: 拒绝原因

        Returns:
            WorkOrder: 更新后的施工单对象

        Raises:
            ServiceError: 业务逻辑错误
        """
        work_order.refresh_from_db()
        WorkOrderFlowService._validate_approval_actor(
            work_order=work_order,
            user=rejected_by,
        )
        WorkOrderFlowService._validate_status_transition(
            work_order.approval_status, WorkOrderApprovalStatus.REJECTED
        )

        # 1. 状态转换
        work_order.approval_status = WorkOrderApprovalStatus.REJECTED
        work_order.approved_by = rejected_by
        work_order.approved_at = timezone.now()
        work_order.approval_comment = reason
        work_order.status = WorkOrderStatus.PENDING  # 状态回到待开始
        work_order.save()

        # 2. 记录拒绝日志
        WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            approval_status=WorkOrderApprovalStatus.REJECTED,
            approved_by=rejected_by,
            approval_comment=reason,
            rejection_reason=reason,
        )

        # 3. 发送通知
        NotificationTriggers.notify_approval_rejected(
            work_order=work_order,
            recipient=work_order.created_by,
            reason=reason,
        )

        return work_order

    # ========== 流程 5: 任务完成后的施工单状态更新 ==========

    @staticmethod
    @transaction.atomic
    def check_and_complete_workorder(*, work_order: WorkOrder) -> bool:
        """
        检查施工单是否所有任务都已完成，如是则标记施工单为已完成

        Args:
            work_order: 施工单对象

        Returns:
            bool: 是否标记为已完成
        """
        if work_order.status != WorkOrderStatus.IN_PROGRESS:
            return False

        # 检查是否所有任务都已完成
        total_tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order
        ).count()
        completed_tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order, status=TaskStatus.COMPLETED
        ).count()

        if total_tasks == completed_tasks and total_tasks > 0:
            work_order.status = WorkOrderStatus.COMPLETED
            work_order.save()

            # 记录日志
            WorkOrderApprovalLog.objects.create(
                work_order=work_order,
                approval_status=work_order.approval_status,
                approval_comment="所有任务已完成，自动标记施工单为完成状态",
            )

            # 发送通知
            NotificationTriggers.notify_workorder_completed(work_order)

            logger.info(
                f"施工单 {work_order.order_number} 所有任务已完成，自动标记为完成"
            )
            return True

        return False

    # ========== 辅助方法 ==========

    @staticmethod
    def _generate_order_number() -> str:
        """生成施工单号（格式：WO20260303001）"""
        today = timezone.now().strftime("%Y%m%d")
        prefix = f"WO{today}"

        # 查找今天最大的序号
        last_order = (
            WorkOrder.objects.filter(order_number__startswith=prefix)
            .order_by("-order_number")
            .first()
        )

        if last_order:
            last_seq = int(last_order.order_number[-3:])
            new_seq = last_seq + 1
        else:
            new_seq = 1

        return f"{prefix}{new_seq:03d}"

    @staticmethod
    def _copy_sales_order_products(
        work_order: WorkOrder,
        sales_order: SalesOrder,
        production_items: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """复制客户订单产品到施工单。"""
        if production_items is None:
            production_items = WorkOrderFlowService._build_production_items(sales_order)

        created_count = 0
        for item in production_items:
            WorkOrderProduct.objects.create(
                work_order=work_order,
                product=item["product"],
                quantity=item["produce_quantity"],
                unit=item["unit"],
                source_type="sales_order",
                sales_order_item=item.get("sales_order_item"),
            )
            created_count += 1

        logger.info(
            f"复制了 {created_count} 个客户订单产品到施工单 {work_order.order_number}"
        )

    @staticmethod
    def _build_selected_production_items(
        sales_order: SalesOrder,
        *,
        selected_items: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """根据用户选择的订单明细生成待生产产品。"""
        if not selected_items:
            return []

        sales_items = {
            item.id: item
            for item in SalesOrderItem.objects.select_related("product").filter(
                sales_order=sales_order
            )
        }
        allocated_quantities = {
            item["sales_order_item_id"]: item["total_quantity"] or 0
            for item in WorkOrderProduct.objects.filter(
                sales_order_item_id__in=sales_items.keys(),
                source_type="sales_order",
            )
            .values("sales_order_item_id")
            .annotate(total_quantity=Sum("quantity"))
        }

        production_items = []
        for index, item in enumerate(selected_items, start=1):
            if not isinstance(item, dict):
                raise ServiceError(
                    f"第 {index} 个施工单产品配置无效", code=status.HTTP_400_BAD_REQUEST
                )

            sales_order_item_id = item.get("sales_order_item_id")
            sales_item = sales_items.get(sales_order_item_id)
            if sales_item is None:
                raise ServiceError(
                    f"第 {index} 个订单产品不存在或不属于当前订单",
                    code=status.HTTP_400_BAD_REQUEST,
                )

            try:
                produce_quantity = int(item.get("production_quantity"))
            except (TypeError, ValueError) as exc:
                raise ServiceError(
                    f"第 {index} 个订单产品生产数量无效",
                    code=status.HTTP_400_BAD_REQUEST,
                ) from exc

            remaining_quantity = max(
                int(sales_item.quantity)
                - int(allocated_quantities.get(sales_item.id, 0) or 0),
                0,
            )
            if produce_quantity <= 0:
                raise ServiceError(
                    f"{sales_item.product.name} 的生产数量必须大于 0",
                    code=status.HTTP_400_BAD_REQUEST,
                )
            if produce_quantity > remaining_quantity:
                raise ServiceError(
                    f"{sales_item.product.name} 的生产数量不能超过剩余可开数量 {remaining_quantity}",
                    code=status.HTTP_400_BAD_REQUEST,
                )

            production_items.append(
                {
                    "sales_order_item": sales_item,
                    "product": sales_item.product,
                    "unit": sales_item.unit,
                    "produce_quantity": produce_quantity,
                    "sales_quantity": sales_item.quantity,
                    "available_quantity": 0,
                }
            )

        return production_items

    @staticmethod
    def _build_production_items(
        sales_order: SalesOrder,
    ) -> List[Dict[str, Any]]:
        """根据库存缺口计算需要生产的客户订单明细"""
        sales_items = list(
            SalesOrderItem.objects.select_related("product").filter(
                sales_order=sales_order
            )
        )
        if not sales_items:
            return []

        allocated_quantities = {
            item["sales_order_item_id"]: item["total_quantity"] or 0
            for item in WorkOrderProduct.objects.filter(
                sales_order_item_id__in=[item.id for item in sales_items],
                source_type="sales_order",
            )
            .values("sales_order_item_id")
            .annotate(total_quantity=Sum("quantity"))
        }

        product_ids = {item.product_id for item in sales_items if item.product_id}

        stock_totals = (
            ProductStock.objects.filter(product_id__in=product_ids)
            .values("product_id")
            .annotate(available_quantity=Sum(F("quantity") - F("reserved_quantity")))
        )
        available_map = {}
        for item in stock_totals:
            qty = item["available_quantity"] or 0
            if qty < 0:
                qty = 0
            available_map[item["product_id"]] = qty

        production_items = []
        for item in sales_items:
            unallocated_quantity = max(
                int(item.quantity) - int(allocated_quantities.get(item.id, 0) or 0),
                0,
            )
            if unallocated_quantity <= 0:
                continue
            available_qty = available_map.get(item.product_id, 0)
            needed_qty = max(unallocated_quantity - int(available_qty), 0)
            if needed_qty <= 0:
                continue
            production_items.append(
                {
                    "sales_order_item": item,
                    "product": item.product,
                    "unit": item.unit,
                    "produce_quantity": needed_qty,
                    "sales_quantity": item.quantity,
                    "available_quantity": available_qty,
                }
            )

        return production_items

    @staticmethod
    def _auto_generate_processes(work_order: WorkOrder) -> None:
        """根据产品配置自动生成工序（带版本快照）"""
        products = work_order.products.select_related("product").all()

        # 收集工序及其来源产品，Product.default_processes 直接关联 Process。
        process_config_map = {}
        for product_item in products:
            default_processes = product_item.product.default_processes.all()
            for process in default_processes:
                if process.id not in process_config_map:
                    process_config_map[process.id] = (process, product_item.product)

        # 批量创建工序（含快照数据）
        work_order_processes = []
        for index, (process_id, (process, product)) in enumerate(
            sorted(process_config_map.items(), key=lambda x: x[0]), 1
        ):
            # 创建工序快照数据
            process_snapshot = {
                "process_id": process.id,
                "process_code": process.code,
                "process_name": process.name,
                "department_id": None,
                "department_name": None,
                "is_parallel": getattr(process, "is_parallel", False),
                "requires_artwork": getattr(process, "requires_artwork", False),
                "source_product_id": product.id,
                "source_product_name": product.name,
                "source_product_code": product.code,
            }

            work_order_processes.append(
                WorkOrderProcess(
                    work_order=work_order,
                    process=process,
                    sequence=index,
                    source_product_process_id=None,
                    process_snapshot=process_snapshot,
                    source_version="1.0",
                )
            )

        WorkOrderProcess.objects.bulk_create(work_order_processes)
        logger.info(
            f"为施工单 {work_order.order_number} 自动生成了 {len(work_order_processes)} 个工序（含版本快照）"
        )

    @staticmethod
    def _auto_generate_materials(work_order: WorkOrder) -> None:
        """根据产品配置自动生成物料"""
        products = work_order.products.select_related("product").all()

        for product_item in products:
            # 获取产品的默认物料
            product_materials = product_item.product.default_materials.all()

            for product_material in product_materials:
                # 创建施工单物料
                WorkOrderMaterial.objects.create(
                    work_order=work_order,
                    material=product_material.material,
                    material_size=product_material.material_size,
                    material_usage=product_material.material_usage,
                    need_cutting=product_material.need_cutting,
                    notes=f"从产品 {product_item.product.name} 自动生成",
                )

        logger.info(f"为施工单 {work_order.order_number} 自动生成了物料清单")

    @staticmethod
    def _link_assets(work_order: WorkOrder, additional_data: Dict[str, Any]) -> None:
        """关联资产（图稿、刀模等）"""
        # 图稿
        if "artwork_ids" in additional_data:
            work_order.artworks.set(additional_data["artwork_ids"])

        # 刀模
        if "die_ids" in additional_data:
            work_order.dies.set(additional_data["die_ids"])

        # 烫金版
        if "foiling_plate_ids" in additional_data:
            work_order.foiling_plates.set(additional_data["foiling_plate_ids"])

        # 压凸版
        if "embossing_plate_ids" in additional_data:
            work_order.embossing_plates.set(additional_data["embossing_plate_ids"])

        logger.info(f"为施工单 {work_order.order_number} 关联了资产")

    @staticmethod
    def _auto_dispatch_tasks(work_order: WorkOrder) -> Dict[str, Any]:
        """
        自动分派施工单的所有任务

        Args:
            work_order: 施工单对象

        Returns:
            Dict: 分派结果
            {
                'dispatched_count': int,  # 已分派数量
                'total_count': int,       # 总任务数
                'notified_operators': [],  # 已通知的操作员ID列表
                'operator_tasks': {},      # 操作员ID -> 任务数映射
            }
        """
        # 获取所有未分派的正式任务
        tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order,
            status=TaskStatus.PENDING,
            assigned_department__isnull=True,
        )

        dispatched_count = 0
        notified_operators = set()
        operator_tasks = {}

        # 遍历任务并自动分派
        for task in tasks:
            department = AutoDispatchService.dispatch_task(task)

            if department:
                task.assigned_department = department
                task.save()
                dispatched_count += 1

                # 如果指定了操作员，记录
                if task.assigned_operator:
                    notified_operators.add(task.assigned_operator.id)
                    operator_tasks[task.assigned_operator.id] = (
                        operator_tasks.get(task.assigned_operator.id, 0) + 1
                    )

        return {
            "dispatched_count": dispatched_count,
            "total_count": tasks.count(),
            "notified_operators": list(notified_operators),
            "operator_tasks": operator_tasks,
        }
