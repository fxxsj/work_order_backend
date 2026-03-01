"""
服务层异常

用于在 services 层向 views 层传递可控的错误信息与 HTTP 状态码，
以保持 API 响应结构不变，同时将业务逻辑下沉到服务层。
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ServiceError(Exception):
    def __init__(self, message: str, code: int = 400, data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.data = data

