"""
自定义分页类

解决默认 PageNumberPagination 不支持前端自定义 page_size 的问题
"""

from rest_framework.pagination import PageNumberPagination


class CustomPagination(PageNumberPagination):
    """
    自定义分页类，支持前端通过 page_size 参数指定每页数量

    使用方式：
    - 默认每页 20 条
    - 前端可通过 ?page_size=100 指定每页数量
    - 最大限制 200 条，防止复杂序列化和大响应拖慢接口

    示例：
    - /api/processes/?page=1&page_size=100  # 获取第1页，每页100条
    - /api/processes/?page_size=200         # 获取较大页（最多200条）
    """

    page_size = 20  # 默认每页数量
    page_size_query_param = "page_size"  # 允许前端指定每页数量的参数名
    max_page_size = 200  # 最大每页数量限制
