"""
统一的 API 响应格式
"""

from typing import Any, Dict, Optional, Union
from rest_framework.response import Response

from .response_format import build_error_payload, build_success_payload


class APIResponse:
    """统一的 API 响应格式"""

    @staticmethod
    def success(data: Any = None, message: str = '操作成功', code: int = 200) -> Response:
        """成功响应"""
        if isinstance(data, dict) and "message" in data and "data" in data and message == "操作成功":
            message = data.get("message") or message
            data = data.get("data")
        return Response(
            build_success_payload(data=data, message=message, code=code),
            status=code,
        )

    @staticmethod
    def error(
        message: str,
        code: int = 400,
        errors: Optional[Union[Dict[str, Any], list]] = None,
        data: Any = None,
    ) -> Response:
        """错误响应"""
        normalized_message = message
        normalized_errors = errors
        normalized_data = data

        if isinstance(data, dict):
            error_text = data.get("error")
            if normalized_errors is None and "errors" in data:
                normalized_errors = data.get("errors")
            if error_text and not normalized_message:
                normalized_message = error_text
            if set(data.keys()) <= {"error", "errors"}:
                normalized_data = None
            elif "error" in data or "errors" in data:
                normalized_data = {
                    key: value
                    for key, value in data.items()
                    if key not in {"error", "errors"}
                }

        return Response(
            build_error_payload(
                message=normalized_message,
                code=code,
                errors=normalized_errors,
                data=normalized_data,
            ),
            status=code,
        )
