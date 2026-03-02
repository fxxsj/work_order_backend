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

    @staticmethod
    def paginated(queryset, page: int = 1, page_size: int = 20, serializer_class=None, context: Dict = None) -> Response:
        """分页响应"""
        from django.core.paginator import Paginator

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        if serializer_class:
            items = serializer_class(page_obj.object_list, many=True, context=context or {}).data
        else:
            items = list(page_obj.object_list)

        return APIResponse.success(
            {
                'items': items,
                'pagination': {
                    'current_page': page,
                    'page_size': page_size,
                    'total_items': paginator.count,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                    'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
                    'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
                },
            }
        )
