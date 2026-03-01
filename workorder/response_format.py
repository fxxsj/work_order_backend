"""
响应格式工具

集中维护标准响应结构，避免 APIResponse 与 StandardJSONRenderer 重复实现相同逻辑。
注意：此模块只做格式构造/提取，不改变现有对外响应内容。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

from django.utils import timezone


def _timestamp() -> str:
    return timezone.now().isoformat()


def is_standard_payload(data: Any) -> bool:
    return (
        isinstance(data, dict)
        and data.get("success") in (True, False)
        and "message" in data
    )


def build_success_payload(
    *,
    data: Any = None,
    message: str = "操作成功",
    code: int = 200,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "success": True,
        "code": code,
        "message": message,
        "data": data,
        "timestamp": timestamp or _timestamp(),
    }


def build_error_payload(
    *,
    message: str,
    code: int = 400,
    errors: Optional[Union[Dict[str, Any], list]] = None,
    data: Any = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "success": False,
        "code": code,
        "message": message,
        "errors": errors or {},
        "data": data,
        "timestamp": timestamp or _timestamp(),
    }


def extract_first_error_message(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return None

    for key, value in data.items():
        if isinstance(value, list) and value:
            return f"{key}: {value[0]}"
        if isinstance(value, str) and value:
            return f"{key}: {value}"
        if isinstance(value, dict):
            nested = extract_first_error_message(value)
            if nested:
                return f"{key}: {nested}"

    if "detail" in data and isinstance(data["detail"], str):
        return data["detail"]
    if "non_field_errors" in data and isinstance(data["non_field_errors"], list):
        if data["non_field_errors"]:
            return str(data["non_field_errors"][0])
    return None


def standardize_renderer_payload(*, data: Any, status_code: int) -> Any:
    """
    StandardJSONRenderer 的封装逻辑抽出为纯函数，方便复用与测试。

    返回值:
      - 若 data 为 None 或已是标准 payload：原样返回
      - 否则：返回标准 payload 字典
    """
    if data is None:
        return data

    if is_standard_payload(data):
        return data

    timestamp = _timestamp()

    if status_code >= 400:
        message = None
        errors: Any = {}

        if isinstance(data, dict):
            message = data.get("message") or data.get("error") or data.get("detail")
            errors = data
        else:
            message = str(data)
            errors = {"detail": data}

        if not message and isinstance(data, dict):
            message = extract_first_error_message(data)

        if not message:
            message = "请求失败"

        return build_error_payload(
            message=message,
            code=status_code,
            errors=errors,
            data=None,
            timestamp=timestamp,
        )

    message = "操作成功"
    payload_data = data
    if isinstance(data, dict) and "message" in data and "data" in data:
        message = data.get("message") or message
        payload_data = data.get("data")

    return build_success_payload(
        data=payload_data,
        message=message,
        code=status_code,
        timestamp=timestamp,
    )

