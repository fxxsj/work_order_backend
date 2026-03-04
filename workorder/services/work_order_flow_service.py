"""
施工单业务流程编排服务 (WorkOrderFlowService)

负责编排施工单的完整业务流程，包括：
- 从销售订单创建施工单
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
from django.db.models import Sum
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

from ..models.core import (
    WorkOrder,
    WorkOrderProcess,
    WorkOrderTask,
    WorkOrderProduct,
    WorkOrderMaterial,
    APPROVED_ORDER_EDITABLE_FIELDS,
)
from ..models.sales import SalesOrder, SalesOrderItem
from ..models.system import (
    WorkOrderApprovalLog,
    Notification,
    TaskAssignmentRule,
)
from ..models.base import Customer, Department
from .service_errors import ServiceError
from .work_order_service import WorkOrderService
from .task_generation import DraftTaskGenerationService
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
        "pending": ["pending", "approved", "rejected"],
        "rejected": ["pending"],
        "approved": [],
    }

    @staticmethod
    def _validate_status_transition(
        current_status: str, new_status: str
    ) -> None:
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
                code=400,  # HTTP 400 Bad Request
            )

    # ========== 流程 1: 从销售订单创建施工单 ==========

    @staticmethod
    @transaction.atomic
    def create_from_sales_order(
        *,
        sales_order_id: int,
        production_quantity: Optional[int],
        delivery_date: Optional[datetime] = None,
        priority: str = "normal",
        notes: str = "",
        created_by: User,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> WorkOrder:
        """
        从销售订单创建施工单（完整流程）

        流程步骤：
        1. 验证销售订单状态
        2. 复制客户、产品信息
        3. 根据产品配置自动生成工序
        4. 根据产品配置自动生成物料清单
        5. 生成草稿任务（不立即分派）
        6. 记录操作日志
        7. 发送通知

        Args:
            sales_order_id: 销售订单ID
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
        # 1. 加载并验证销售订单
        try:
            sales_order = SalesOrder.objects.select_related("customer").get(
                id=sales_order_id
            )
        except SalesOrder.DoesNotExist as exc:
            raise ServiceError(
                "销售订单不存在", code=404
            ) from exc

        if sales_order.status != "approved":
            raise ServiceError(
                f"只有已审核的销售订单才能创建施工单，当前状态：{sales_order.status}",
                code=400,
            )

        if production_quantity is None:
            production_quantity = (
                sales_order.items.aggregate(total=Sum("quantity"))["total"] or 0
            )

        if production_quantity <= 0:
            raise ServiceError("销售订单没有可生产数量", code=400)

        # 2. 生成施工单号
        order_number = WorkOrderFlowService._generate_order_number()

        # 3. 创建施工单
        work_order = WorkOrder.objects.create(
            order_number=order_number,
            customer=sales_order.customer,
            production_quantity=production_quantity,
            delivery_date=delivery_date or sales_order.delivery_date,
            priority=priority,
            notes=notes,
            created_by=created_by,
            status="pending",  # 初始状态
            approval_status="pending",  # 待审核
        )

        logger.info(f"从销售订单 {sales_order.order_number} 创建施工单 {order_number}")

        # 4. 复制销售订单产品
        WorkOrderFlowService._copy_sales_order_products(work_order, sales_order)

        # 5. 根据产品配置自动生成工序
        WorkOrderFlowService._auto_generate_processes(work_order)

        # 6. 根据产品配置自动生成物料
        WorkOrderFlowService._auto_generate_materials(work_order)

        # 7. 关联资产（图稿、刀模等）
        if additional_data:
            WorkOrderFlowService._link_assets(work_order, additional_data)

        # 8. 生成草稿任务（不立即分派）
        draft_task_count = DraftTaskGenerationService.generate_draft_tasks(work_order)
        logger.info(f"施工单 {order_number} 生成了 {draft_task_count} 个草稿任务")

        # 9. 记录操作日志
        WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            approval_status=work_order.approval_status,
            approved_by=created_by,
            approval_comment=f"从销售订单 {sales_order.order_number} 自动创建",
        )

        # 10. 发送通知
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
    ) -> WorkOrder:
        """
        提交施工单审核（完整流程）

        流程步骤：
        1. 验证施工单状态（必须是待审核）
        2. 验证施工单数据完整性（图稿、工序等）
        3. 状态转换：pending → pending（提交审核）
        4. 记录提交日志
        5. 发送审核通知给业务员
        6. 创建审核任务

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
            raise ServiceError("施工订单不存在", code=404) from exc

        # 2. 验证状态
        WorkOrderFlowService._validate_status_transition(
            work_order.approval_status, "pending"
        )

        # 3. 验证数据完整性
        validation_errors = work_order.validate_before_approval()
        if validation_errors:
            raise ServiceError(
                "施工单数据不完整，无法提交审核",
                code=400,
                data={"details": validation_errors},
            )

        # 4. 状态转换
        work_order.approval_status = "pending"
        work_order.save()

        logger.info(f"施工单 {work_order.order_number} 提交审核")

        # 5. 记录操作日志
        WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            approval_status=work_order.approval_status,
            approved_by=submitted_by,
            approval_comment=comment or "提交审核",
        )

        # 6. 发送通知给业务员
        salesperson = work_order.customer.salesperson
        if salesperson:
            NotificationTriggers.notify_approval_requested(
                work_order=work_order,
                recipient=salesperson,
                comment=comment,
            )

        # 7. 创建审核任务（如果有多级审核）
        # WorkOrderFlowService._create_approval_tasks(work_order)

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
        1. 验证并转换审核状态
        2. 转换草稿任务为正式任务
        3. 自动分派任务到部门和操作员
        4. 状态转换：pending_approval → approved → in_progress
        5. 记录审核日志
        6. 发送通知给相关部门和操作员
        7. 触发库存预留（如有需要）

        Args:
            work_order: 施工单对象
            approved_by: 审核人
            comment: 审核意见

        Returns:
            WorkOrder: 更新后的施工单对象

        Raises:
            ServiceError: 业务逻辑错误
        """
        logger.info(f"开始处理施工单 {work_order.order_number} 的审核通过流程")

        # 1. 转换草稿任务为正式任务
        converted_count = work_order.convert_draft_tasks()
        logger.info(
            f"施工单 {work_order.order_number} 转换了 {converted_count} 个草稿任务"
        )

        # 2. 自动分派任务
        dispatch_result = WorkOrderFlowService._auto_dispatch_tasks(work_order)
        logger.info(
            f"施工单 {work_order.order_number} 自动分派了 {dispatch_result['dispatched_count']} 个任务"
        )

        # 3. 状态转换
        work_order.approval_status = "approved"
        work_order.approved_by = approved_by
        work_order.approved_at = timezone.now()
        work_order.approval_comment = comment
        work_order.status = "in_progress"
        work_order.save()

        # 4. 记录审核日志
        WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            approval_status=work_order.approval_status,
            approved_by=approved_by,
            approval_comment=comment,
        )

        # 5. 发送通知
        NotificationTriggers.notify_approval_passed(
            work_order=work_order,
            dispatch_result=dispatch_result,
        )

        # 6. 触发库存预留
        # WorkOrderFlowService._reserve_materials(work_order)

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
        1. 删除所有草稿任务
        2. 状态转换：pending → rejected
        3. 记录拒绝日志
        4. 发送通知给创建人

        Args:
            work_order: 施工单对象
            rejected_by: 审核人
            reason: 拒绝原因

        Returns:
            WorkOrder: 更新后的施工单对象

        Raises:
            ServiceError: 业务逻辑错误
        """
        # 1. 删除草稿任务
        deleted_count = work_order.delete_draft_tasks()
        logger.info(
            f"施工单 {work_order.order_number} 删除了 {deleted_count} 个草稿任务"
        )

        # 2. 状态转换
        work_order.approval_status = "rejected"
        work_order.approved_by = rejected_by
        work_order.approved_at = timezone.now()
        work_order.approval_comment = reason
        work_order.save()

        # 3. 记录拒绝日志
        WorkOrderApprovalLog.objects.create(
            work_order=work_order,
            approval_status=work_order.approval_status,
            approved_by=rejected_by,
            approval_comment=reason,
            rejection_reason=reason,
        )

        # 4. 发送通知
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
        if work_order.status != "in_progress":
            return False

        # 检查是否所有任务都已完成
        total_tasks = WorkOrderTask.objects.filter(work_order_process__work_order=work_order).count()
        completed_tasks = WorkOrderTask.objects.filter(
            work_order_process__work_order=work_order,
            status="completed"
        ).count()

        if total_tasks == completed_tasks and total_tasks > 0:
            work_order.status = "completed"
            work_order.save()

            # 记录日志
            WorkOrderApprovalLog.objects.create(
                work_order=work_order,
                approval_status=work_order.approval_status,
                approval_comment="所有任务已完成，自动标记施工单为完成状态",
            )

            # 发送通知
            NotificationTriggers.notify_workorder_completed(work_order)

            logger.info(f"施工单 {work_order.order_number} 所有任务已完成，自动标记为完成")
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
        work_order: WorkOrder, sales_order: SalesOrder
    ) -> None:
        """复制销售订单产品到施工单"""
        sales_items = SalesOrderItem.objects.filter(sales_order=sales_order)

        for item in sales_items:
            WorkOrderProduct.objects.create(
                work_order=work_order,
                product=item.product,
                quantity=item.quantity,
                unit=item.unit,
            )

        logger.info(
            f"复制了 {sales_items.count()} 个销售订单产品到施工单 {work_order.order_number}"
        )

    @staticmethod
    def _auto_generate_processes(work_order: WorkOrder) -> None:
        """根据产品配置自动生成工序"""
        products = work_order.products.select_related("product").all()
        process_set = set()

        for product_item in products:
            # 获取产品的默认工序
            product_processes = product_item.product.default_processes.all()
            for process in product_processes:
                process_set.add(process)

        # 批量创建工序
        work_order_processes = [
            WorkOrderProcess(
                work_order=work_order,
                process=process,
                sequence=index,
            )
            for index, process in enumerate(sorted(process_set, key=lambda p: p.id), 1)
        ]

        WorkOrderProcess.objects.bulk_create(work_order_processes)
        logger.info(
            f"为施工单 {work_order.order_number} 自动生成了 {len(work_order_processes)} 个工序"
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

        logger.info(
            f"为施工单 {work_order.order_number} 自动生成了物料清单"
        )

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
            status="pending",
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
            'dispatched_count': dispatched_count,
            'total_count': tasks.count(),
            'notified_operators': list(notified_operators),
            'operator_tasks': operator_tasks,
        }
