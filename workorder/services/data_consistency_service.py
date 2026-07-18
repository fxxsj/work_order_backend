"""
数据一致性检查服务

提供库存、施工单数量、工序数量、付款状态的日常一致性检查，
返回差异项和可修复建议。
"""

import logging
from decimal import Decimal
from typing import Dict, Any

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

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
                    {"name": str, "status": "ok|warning|error",
                     "issues": [...]}
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

        issues = []
        products = Product.objects.annotate(
            batch_total=Coalesce(
                Sum(
                    "productstock__quantity",
                    filter=Q(productstock__status="in_stock"),
                ),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )

        for product in products:
            batch_total = product.batch_total
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
        from workorder.models.core import WorkOrder

        issues = []
        work_orders = WorkOrder.objects.filter(status="completed").annotate(
            task_count=Count("order_processes__tasks"),
            total_completed=Coalesce(
                Sum("order_processes__tasks__quantity_completed"),
                Value(0),
            ),
        )

        for wo in work_orders:
            if not wo.task_count:
                continue

            total_completed = wo.total_completed
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
        sales_orders = SalesOrder.objects.annotate(
            total_applied=Coalesce(
                Sum("payments__applied_amount"),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )

        for so in sales_orders:
            total_applied = so.total_applied
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
                        "suggestion": (
                            "请运行 PaymentService.apply_payment() 重新计算"
                        ),
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
        from workorder.models.core import WorkOrderProcess

        issues = []
        processes = (
            WorkOrderProcess.objects.filter(status="completed")
            .select_related("work_order", "process")
            .annotate(
                incomplete_task_count=Count(
                    "tasks",
                    filter=~Q(tasks__status="completed"),
                )
            )
            .filter(incomplete_task_count__gt=0)
        )

        for process in processes:
            issues.append(
                {
                    "severity": "critical",
                    "type": "process_task_mismatch",
                    "work_order_id": process.work_order.id,
                    "work_order_number": process.work_order.order_number,
                    "process_id": process.id,
                    "process_name": process.process.name,
                    "incomplete_task_count": process.incomplete_task_count,
                    "suggestion": "请检查工序完成条件或手动完成任务",
                }
            )

        return {
            "name": "任务工序一致性",
            "status": "ok" if not issues else "error",
            "issues": issues,
        }
