"""
自定义速率限制类

为不同的 API 操作提供细粒度的速率限制控制
"""
from rest_framework.throttling import SimpleRateThrottle


class ApprovalRateThrottle(SimpleRateThrottle):
    """审核操作速率限制

    限制审核操作的频率，防止滥用
    """
    scope = 'approval'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return f'approval_{ident}'


class ExportRateThrottle(SimpleRateThrottle):
    """导出操作速率限制

    限制导出操作的频率，防止资源消耗过大
    """
    scope = 'export'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return f'export_{ident}'


class CreateRateThrottle(SimpleRateThrottle):
    """创建操作速率限制

    限制创建操作的频率，防止恶意批量创建
    """
    scope = 'create'
    rate = '30/hour'  # 每小时最多 30 次创建操作

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return f'create_{ident}'


class BurstRateThrottle(SimpleRateThrottle):
    """突发速率限制

    用于限制短时间内的突发请求
    """
    scope = 'burst'
    rate = '10/minute'  # 每分钟最多 10 次请求

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return f'burst_{ident}'
