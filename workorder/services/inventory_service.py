"""
库存管理服务

提供统一的库存管理接口，确保库存操作的安全性和一致性
"""

from django.db import transaction
from workorder.exceptions import InsufficientStockError, BusinessLogicError
import logging

logger = logging.getLogger(__name__)


class InventoryService:
    """库存管理服务"""

    @staticmethod
    @transaction.atomic
    def add_stock(item, quantity, user=None, reason=''):
        """
        增加库存

        Args:
            item: 库存项目（Product 或 Material）
            quantity: 增加数量
            user: 操作用户
            reason: 增加原因

        Returns:
            bool: 操作是否成功

        Raises:
            BusinessLogicError: 库存更新失败
        """
        try:
            if quantity <= 0:
                raise ValueError("增加数量必须大于0")

            # 更新库存
            item.current_stock += quantity
            item.save()

            # 记录日志
            user_info = f", 操作人: {user}" if user else ""
            logger.info(
                f"库存增加: {item.__class__.__name__} - {item.name} "
                f"+{quantity} -> {item.current_stock}, 原因: {reason}{user_info}"
            )

            return True

        except Exception as e:
            logger.error(
                f"库存增加失败: {item.__class__.__name__} - {item.name}, "
                f"数量: {quantity}, 错误: {str(e)}"
            )
            raise BusinessLogicError(f"库存增加失败: {str(e)}")

    @staticmethod
    @transaction.atomic
    def reduce_stock(item, quantity, user=None, reason=''):
        """
        减少库存

        Args:
            item: 库存项目（Product 或 Material）
            quantity: 减少数量
            user: 操作用户
            reason: 减少原因

        Returns:
            bool: 操作是否成功

        Raises:
            InsufficientStockError: 库存不足
            BusinessLogicError: 其他业务错误
        """
        try:
            if quantity <= 0:
                raise ValueError("减少数量必须大于0")

            # 检查库存是否充足
            if item.current_stock < quantity:
                raise InsufficientStockError(
                    f"{item.name} 库存不足。"
                    f"当前库存: {item.current_stock}, 需要: {quantity}"
                )

            # 更新库存
            item.current_stock -= quantity
            item.save()

            # 记录日志
            user_info = f", 操作人: {user}" if user else ""
            logger.info(
                f"库存减少: {item.__class__.__name__} - {item.name} "
                f"-{quantity} -> {item.current_stock}, 原因: {reason}{user_info}"
            )

            return True

        except InsufficientStockError:
            # 重新抛出业务异常
            raise
        except Exception as e:
            logger.error(
                f"库存减少失败: {item.__class__.__name__} - {item.name}, "
                f"数量: {quantity}, 错误: {str(e)}"
            )
            raise BusinessLogicError(f"库存减少失败: {str(e)}")

    @staticmethod
    def get_stock_status(item):
        """
        获取库存状态

        Args:
            item: 库存项目

        Returns:
            dict: 库存状态信息
        """
        return {
            'current_stock': item.current_stock,
            'min_stock': item.min_stock if hasattr(item, 'min_stock') else 0,
            'is_low_stock': item.current_stock < (item.min_stock if hasattr(item, 'min_stock') else 0),
            'status': 'normal' if item.current_stock >= (item.min_stock if hasattr(item, 'min_stock') else 0) else 'low'
        }

    @staticmethod
    def check_stock_availability(items_quantities):
        """
        检查多个项目的库存是否充足

        Args:
            items_quantities: 列表，元素为 (item, quantity) 元组

        Returns:
            dict: {item: insufficient_quantity} 不充足的库存项
        """
        insufficient = {}

        for item, quantity in items_quantities:
            if item.current_stock < quantity:
                insufficient[item] = quantity - item.current_stock

        return insufficient
