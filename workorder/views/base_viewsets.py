"""
基础视图集类

提供通用的 ViewSet 基类，减少代码重复。
所有视图集都应继承这些基类以获得一致的功能。
"""

from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend

from ..permissions import SuperuserFriendlyModelPermissions


class BaseViewSet(viewsets.ModelViewSet):
    """
    基础视图集

    提供标准的配置和功能，所有需要完整 CRUD 操作的视图集应继承此类。

    特性:
        - 标准的 filter_backends (DjangoFilterBackend, SearchFilter, OrderingFilter)
        - 标准的权限控制 (SuperuserFriendlyModelPermissions)
        - 自动的查询优化 (select_related)

    使用示例:
        class MyViewSet(BaseViewSet):
            serializer_class = MySerializer
            filterset_fields = ['field1', 'field2']
            search_fields = ['name', 'description']
    """

    # 标准的过滤器后端
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # 标准的权限类
    permission_classes = [SuperuserFriendlyModelPermissions]

    def get_queryset(self):
        """
        获取查询集，子类可以重写此方法添加特定的查询优化。

        默认实现：返回模型的默认查询集。
        """
        queryset = super().get_queryset()

        # 子类可以在这里添加查询优化，例如：
        # queryset = queryset.select_related('foreign_key_field')
        # queryset = queryset.prefetch_related('many_to_many_field')

        return queryset


class ReadOnlyBaseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    只读基础视图集

    用于只需要读取（list, retrieve）操作的视图集。
    继承此类后，视图集将自动禁用创建、更新和删除操作。

    使用示例:
        class PublicDataViewSet(ReadOnlyBaseViewSet):
            serializer_class = PublicDataSerializer
            filterset_fields = ['category']
    """

    # 标准的过滤器后端
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # 标准的权限类
    permission_classes = [SuperuserFriendlyModelPermissions]

    def get_queryset(self):
        """获取查询集（只读）"""
        queryset = super().get_queryset()
        return queryset
