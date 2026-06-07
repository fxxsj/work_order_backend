"""
数据一致性检查服务

提供库存、施工单数量、工序数量、付款状态的日常一致性检查，
返回差异项和可修复建议。
"""

import logging
from decimal import Decimal
from typing import Dict, List, Any

from django.db.models import Sum

logger = logging.getLogger(__name__)


class DataConsistencyService:
    """数据一致性检查服务"""

    @staticmethod
    def run_all_checks() -> Dict[str, Any]:
        """
        运行所有一致性检查。

        Returns:
            Dict: {
                "summary": {"total_issues": int, "critical_issues": int},
                "checks": [
                    {"name": str, "status": "ok|warning|error", "issues": [...]}
                ]
            }
        """
        checks = [
            DataConsistencyService.check_inventory_consistency(),
            DataConsistencyService.check_work_order_quantity_consistency(),
            DataConsistencyService.check_payment_status_consistency(),
            DataConsistencyService.check_task_process_consistency(),
        ]

        total_issues = sum(len(c["issues"]) for c in checks)
        critical_issues = sum(
            1 for c in checks for i in c["issues"] if i.get("severity") == "critical"
        )

        return {
            "summary": {
                "total_issues": total_issues,
                "critical_issues": critical_issues,
            },
            "checks": checks,
        }

    @staticmethod
    def check_inventory_consistency() -> Dict[str, Any]:
        """检查库存一致性：Product.stock_quantity 与 ProductStock 批次汇总是否一致"""
        from workorder.models.products import Product
        from workorder.models.inventory import ProductStock

        issues = []
        products = Product.objects.all()

        for product in products:
            batch_total = (
                ProductStock.objects.filter(product=product, status="in_stock").aggregate(
                    total=Sum("quantity")
                )["total"]
                or Decimal("0")
            )
            if product.stock_quantity != batch_total:
                issues.append(
                    {
                        "severity": "warning",
                        "type": "inventory_mismatch",
                        "product_id": product.id,
                        "product_name": product.name,
                        "product_stock_quantity": float(product.stock_quantity),
                        "batch_total": float(batch_total),
                        "difference": float(product.stock_quantity - batch_total),
                        "suggestion": "请核对入库和发货记录，使用库存调整功能修正",
                    }
                )

        return {
            "name": "库存一致性",
            "status": "ok" if not issues else "warning",
            "issues": issues,
        }

    @staticmethod
    def check_work_order_quantity_consistency() -> Dict[str, Any]:
        """检查施工单数量一致性：生产数量与所有任务完成数量是否匹配"""
        from workorder.models.core import WorkOrder, WorkOrderTask

        issues = []
        work_orders = WorkOrder.objects.filter(status="completed")

        for wo in work_orders:
            tasks = WorkOrderTask.objects.filter(work_order_process__work_order=wo)
            if not tasks.exists():
                continue

            total_completed = sum(t.quantity_completed or 0 for t in tasks)
            if total_completed != wo.production_quantity:
                issues.append(
                    {
                        "severity": "warning",
                        "type": "quantity_mismatch",
                        "work_order_id": wo.id,
                        "work_order_number": wo.order_number,
                        "production_quantity": wo.production_quantity,
                        "total_completed": total_completed,
                        "difference": wo.production_quantity - total_completed,
                        "suggestion": "请核对任务报工记录",
                    }
                )

        return {
            "name": "施工单数量一致性",
            "status": "ok" if not issues else "warning",
            "issues": issues,
        }

    @staticmethod
    def check_payment_status_consistency() -> Dict[str, Any]:
        """检查付款状态一致性：SalesOrder.paid_amount 与 Payment.applied_amount 汇总是否一致"""
        from workorder.models.sales import SalesOrder

        issues = []
        sales_orders = SalesOrder.objects.all()

        for so in sales_orders:
            total_applied = (
                so.payments.aggregate(total=Sum("applied_amount"))["total"]
                or Decimal("0")
            )
            if so.paid_amount != total_applied:
                issues.append(
                    {
                        "severity": "critical",
                        "type": "payment_mismatch",
                        "sales_order_id": so.id,
                        "sales_order_number": so.order_number,
                        "paid_amount": float(so.paid_amount),
                        "total_applied": float(total_applied),
                        "difference": float(so.paid_amount - total_applied),
                        "suggestion": "请运行 PaymentService.apply_payment() 重新计算",
                    }
                )

        return {
            "name": "付款状态一致性",
            "status": "ok" if not issues else "error",
            "issues": issues,
        }

    @staticmethod
    def check_task_process_consistency() -> Dict[str, Any]:
        """检查任务工序一致性：已完成工序下是否存在未完成任务"""
        from workorder.models.core import WorkOrderProcess, WorkOrderTask

        issues = []
        processes = WorkOrderProcess.objects.filter(status="completed")

        for process in processes:
            incomplete_tasks = WorkOrderTask.objects.filter(
                work_order_process=process,
            ).exclude(status="completed")

            if incomplete_tasks.exists():
                issues.append(
                    {
                        "severity": "critical",
                        "type": "process_task_mismatch",
                        "work_order_id": process.work_order.id,
                        "work_order_number": process.work_order.order_number,
                        "process_id": process.id,
                        "process_name": process.process.name,
                        "incomplete_task_count": incomplete_tasks.count(),
                        "suggestion": "请检查工序完成条件或手动完成任务",
                    }
                )

        return {
            "name": "任务工序一致性",
            "status": "ok" if not issues else "error",
            "issues": issues,
        }
