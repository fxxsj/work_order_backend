"""
服务层异常

ServiceError 是服务层的标准异常，所有 services/ 和 policies/ 层的错误
均应使用 ServiceError 抛出，由视图层统一捕获并转换为 HTTP 响应。

用法::

    raise ServiceError("操作员不存在", code=status.HTTP_404_NOT_FOUND)
    raise ServiceError("库存不足", code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                       data={"current": 10, "required": 20})

注意事项：
- 服务层（services/、policies/）应统一使用 ServiceError
- exceptions.py 中的 APIException 子类仅用于视图层（views/）直接抛出的场景
- 不要在服务层混用两套异常体系，以保持代码风格一致
"""

from __future__ import annotations

from rest_framework import status
from typing import Any, Dict, Optional


class ServiceError(Exception):
    def __init__(
        self,
        message: str,
        code: int | str = status.HTTP_400_BAD_REQUEST,
        data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.data = data

    def __repr__(self):
        return f"ServiceError({self.message!r}, code={self.code!r})"
