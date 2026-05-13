"""
库存更新服务。

处理施工单工序完成时的产品和物料库存更新逻辑。
从 models/core.py 的 WorkOrderProcess 模型中提取，保持模型层职责清晰。
"""

import logging
from django.db import transaction

from workorder.constants.status import MaterialPurchaseStatus, TaskStatus

logger = logging.getLogger(__name__)


class StockUpdateService:
    """产品和物料库存更新服务。"""

    @staticmethod
    def update_product_stock_on_packaging(work_order_process):
        """
        包装工序完成时，更新产品的库存数量。

        规则：
        - 使用事务确保原子性
        - 批量锁定产品记录，避免并发冲突
        - 避免重复计算已入库的数量
        - 记录详细的库存变更日志
        """
        from workorder.models import WorkOrderTask
        from workorder.models.products import Product, ProductStockLog

        with transaction.atomic():
            packaging_tasks = (
                work_order_process.tasks.filter(
                    task_type="packaging", status=TaskStatus.COMPLETED
                )
                .select_related("product")
                .all()
            )

            product_quantities = {}
            task_updates = []

            for task in packaging_tasks:
                if not task.product:
                    continue

                product_id = task.product.id
                actual_quantity = task.quantity_completed - (
                    task.stock_accounted_quantity or 0
                )

                if actual_quantity > 0:
                    product_quantities[product_id] = (
                        product_quantities.get(product_id, 0) + actual_quantity
                    )
                    task.stock_accounted_quantity = task.quantity_completed
                    task_updates.append(task)

            if task_updates:
                WorkOrderTask.objects.bulk_update(
                    task_updates, ["stock_accounted_quantity"]
                )

            if not product_quantities:
                return

            products = Product.objects.select_for_update().filter(
                id__in=product_quantities.keys()
            )
            product_map = {p.id: p for p in products}

            stock_updates = []
            for product_id, quantity in product_quantities.items():
                if product_id not in product_map:
                    logger.warning(
                        f"产品ID {product_id} 不存在，跳过库存更新"
                    )
                    continue

                product = product_map[product_id]
                old_qty = product.stock_quantity
                new_qty = old_qty + quantity
                product.stock_quantity = new_qty
                stock_updates.append((product, old_qty, new_qty, quantity))

            if not stock_updates:
                return

            products_to_update = [item[0] for item in stock_updates]
            Product.objects.bulk_update(products_to_update, ["stock_quantity"])

            log_entries = [
                ProductStockLog(
                    product=item[0],
                    change_type="add",
                    quantity=item[3],
                    old_quantity=item[1],
                    new_quantity=item[2],
                    reason=(
                        f"施工单{work_order_process.work_order.order_number}"
                        f"包装工序完成，入库{item[3]}{item[0].unit}"
                    ),
                    created_by=None,
                )
                for item in stock_updates
            ]
            ProductStockLog.objects.bulk_create(log_entries)

            for product, _, new_qty, _ in stock_updates:
                if product.is_low_stock():
                    product._send_low_stock_warning()

    @staticmethod
    def update_material_stock_on_cutting(work_order_process):
        """
        开料工序完成时，更新物料库存数量。

        规则：
        - 使用事务确保原子性
        - 批量锁定物料记录，避免并发冲突
        - 记录详细的库存变更日志
        """
        from workorder.models import WorkOrderTask
        from workorder.models.core import WorkOrderMaterial
        from workorder.models.materials import Material, MaterialStockLog

        with transaction.atomic():
            cutting_tasks = (
                work_order_process.tasks.filter(
                    task_type="cutting", status=TaskStatus.COMPLETED
                )
                .select_related("material")
                .all()
            )

            material_quantities = {}
            material_updates = []

            for task in cutting_tasks:
                if not task.material:
                    continue

                material_id = task.material.id
                cutting_qty = task.quantity_completed or 0

                if cutting_qty > 0:
                    material_quantities[material_id] = (
                        material_quantities.get(material_id, 0) + cutting_qty
                    )

                    work_order_material = (
                        work_order_process.work_order.materials.filter(
                            material=task.material
                        ).first()
                    )
                    if (
                        work_order_material
                        and work_order_material.purchase_status != MaterialPurchaseStatus.CUT
                    ):
                        work_order_material.purchase_status = MaterialPurchaseStatus.CUT
                        work_order_material.cut_date = (
                            work_order_process.work_order.updated_at.date()
                        )
                        material_updates.append(work_order_material)

            if material_updates:
                WorkOrderMaterial.objects.bulk_update(
                    material_updates, ["purchase_status", "cut_date"]
                )

            if not material_quantities:
                return

            materials = Material.objects.select_for_update().filter(
                id__in=material_quantities.keys()
            )
            material_map = {m.id: m for m in materials}

            stock_updates = []
            for material_id, quantity in material_quantities.items():
                if material_id not in material_map:
                    logger.warning(
                        f"物料ID {material_id} 不存在，跳过库存更新"
                    )
                    continue

                material = material_map[material_id]
                old_qty = material.stock_quantity
                new_qty = old_qty - quantity

                if new_qty < 0:
                    logger.warning(
                        f"物料 {material.name} 库存不足"
                        f"（当前: {old_qty}，需扣减: {quantity}）"
                    )
                    new_qty = 0

                material.stock_quantity = new_qty
                stock_updates.append((material, old_qty, new_qty, quantity))

            if not stock_updates:
                return

            materials_to_update = [item[0] for item in stock_updates]
            Material.objects.bulk_update(
                materials_to_update, ["stock_quantity"]
            )

            log_entries = [
                MaterialStockLog(
                    material=item[0],
                    change_type="cut_consume",
                    quantity=-item[3],
                    old_quantity=item[1],
                    new_quantity=item[2],
                    reason=(
                        f"施工单 {work_order_process.work_order.order_number} "
                        f"开料工序完成，扣减库存{item[3]}{item[0].unit}"
                    ),
                    created_by=None,
                )
                for item in stock_updates
            ]
            MaterialStockLog.objects.bulk_create(log_entries)

            logger.info(
                f"施工单 {work_order_process.work_order.order_number} "
                f"开料工序完成，更新了 {len(stock_updates)} 种物料的库存"
            )
