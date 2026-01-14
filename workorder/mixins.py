"""
视图混入类

提供通用的视图功能
"""

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from workorder.exceptions import BusinessLogicError
import logging

logger = logging.getLogger(__name__)


class TransactionMixin:
    """事务混入类 - 为关键操作提供事务保护"""

    def transactional_create(self, request, *args, **kwargs):
        """带事务的创建操作"""
        try:
            with transaction.atomic():
                return self.create(request, *args, **kwargs)
        except BusinessLogicError as e:
            logger.warning(f"业务逻辑错误: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"创建失败: {str(e)}", exc_info=True)
            return Response(
                {'error': '系统错误，请稍后重试'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def transactional_update(self, request, *args, **kwargs):
        """带事务的更新操作"""
        try:
            with transaction.atomic():
                return self.update(request, *args, **kwargs)
        except BusinessLogicError as e:
            logger.warning(f"业务逻辑错误: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"更新失败: {str(e)}", exc_info=True)
            return Response(
                {'error': '系统错误，请稍后重试'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def transactional_destroy(self, request, *args, **kwargs):
        """带事务的删除操作"""
        try:
            with transaction.atomic():
                return self.destroy(request, *args, **kwargs)
        except BusinessLogicError as e:
            logger.warning(f"业务逻辑错误: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"删除失败: {str(e)}", exc_info=True)
            return Response(
                {'error': '系统错误，请稍后重试'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OptimisticLockMixin:
    """乐观锁混入类 - 处理并发冲突"""

    def check_version_conflict(self, instance, request_data):
        """
        检查版本冲突

        Args:
            instance: 模型实例
            request_data: 请求数据

        Returns:
            Response: 如果有冲突返回错误响应，否则返回 None
        """
        if not hasattr(instance, 'version'):
            return None

        expected_version = request_data.get('version')
        if expected_version is not None:
            current_version = instance.version
            if current_version != int(expected_version):
                return Response(
                    {
                        'error': '数据已被其他用户修改，请刷新后重试',
                        'current_version': current_version,
                        'your_version': int(expected_version)
                    },
                    status=status.HTTP_409_CONFLICT
                )

        return None


class InventoryOperationMixin:
    """库存操作混入类 - 提供安全的库存操作"""

    def safe_stock_operation(self, operation, *args, **kwargs):
        """
        安全的库存操作

        Args:
            operation: 操作函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        try:
            result = operation(*args, **kwargs)
            return True, None
        except Exception as e:
            logger.error(f"库存操作失败: {str(e)}", exc_info=True)
            return False, str(e)

    def handle_stock_adjustment(self, task, new_quantity, user=None):
        """
        处理库存调整

        Args:
            task: 任务实例
            new_quantity: 新的数量
            user: 操作用户

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        if not hasattr(task, 'product') or not task.product:
            return True, None

        # 计算库存差异
        old_quantity = task.stock_accounted_quantity or 0
        stock_increment = new_quantity - old_quantity

        if stock_increment == 0:
            return True, None

        work_order = task.work_order_process.work_order

        try:
            from workorder.services.inventory_service import InventoryService

            if stock_increment > 0:
                # 增加库存
                InventoryService.add_stock(
                    item=task.product,
                    quantity=stock_increment,
                    user=user,
                    reason=f'施工单 {work_order.order_number} 包装任务完成'
                )
            else:
                # 减少库存
                success, error = self.safe_stock_operation(
                    InventoryService.reduce_stock,
                    item=task.product,
                    quantity=abs(stock_increment),
                    user=user,
                    reason=f'施工单 {work_order.order_number} 包装任务数量调整'
                )

                if not success:
                    return False, error

            # 更新已计入库存的数量
            task.stock_accounted_quantity = new_quantity
            task.save(update_fields=['stock_accounted_quantity'])

            return True, None

        except Exception as e:
            logger.error(f"库存调整失败: {str(e)}", exc_info=True)
            return False, f"库存调整失败: {str(e)}"
