"""
自定义异常类

定义业务逻辑异常，提供更清晰的错误处理
"""


class WorkOrderException(Exception):
    """基础异常类"""
    def __init__(self, message, code=None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class InsufficientStockError(WorkOrderException):
    """库存不足异常"""
    pass


class InvalidStatusTransitionError(WorkOrderException):
    """无效的状态转换异常"""
    pass


class DuplicateOrderNumberError(WorkOrderException):
    """订单号重复异常"""
    pass


class BusinessLogicError(WorkOrderException):
    """业务逻辑错误异常"""
    pass


class WorkflowError(WorkOrderException):
    """工作流错误异常"""
    pass


class ValidationError(WorkOrderException):
    """数据验证错误异常"""
    pass
