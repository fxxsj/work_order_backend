"""
统一 JSON 响应渲染器
"""

from django.utils import timezone
from rest_framework.renderers import JSONRenderer


class StandardJSONRenderer(JSONRenderer):
    """
    将所有 JSON 响应统一为标准格式。
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context is None:
            return super().render(data, accepted_media_type, renderer_context)

        response = renderer_context.get('response')
        status_code = getattr(response, 'status_code', 200)

        if data is None:
            return super().render(data, accepted_media_type, renderer_context)

        if isinstance(data, dict) and data.get('success') in (True, False) and 'message' in data:
            return super().render(data, accepted_media_type, renderer_context)

        timestamp = timezone.now().isoformat()

        if status_code >= 400:
            message = None
            errors = {}

            if isinstance(data, dict):
                message = data.get('message') or data.get('error') or data.get('detail')
                errors = data
            else:
                message = str(data)
                errors = {'detail': data}

            if not message:
                message = '请求失败'

            payload = {
                'success': False,
                'code': status_code,
                'message': message,
                'errors': errors,
                'data': None,
                'timestamp': timestamp,
            }
            return super().render(payload, accepted_media_type, renderer_context)

        message = '操作成功'
        payload_data = data
        if isinstance(data, dict):
            if 'message' in data and 'data' in data:
                message = data.get('message') or message
                payload_data = data.get('data')
        payload = {
            'success': True,
            'code': status_code,
            'message': message,
            'data': payload_data,
            'timestamp': timestamp,
        }
        return super().render(payload, accepted_media_type, renderer_context)
