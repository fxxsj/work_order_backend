"""
统一 JSON 响应渲染器
"""

from rest_framework.renderers import JSONRenderer

from .response_format import standardize_renderer_payload


class StandardJSONRenderer(JSONRenderer):
    """
    将所有 JSON 响应统一为标准格式。
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context is None:
            return super().render(data, accepted_media_type, renderer_context)

        response = renderer_context.get('response')
        status_code = getattr(response, 'status_code', 200)

        payload = standardize_renderer_payload(data=data, status_code=status_code)
        return super().render(payload, accepted_media_type, renderer_context)
