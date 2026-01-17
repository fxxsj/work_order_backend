"""
基础数据视图集

包含客户、部门、工序等基础数据的视图集。
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from ..models.base import Customer, Department, Process
from ..serializers.base import CustomerSerializer, DepartmentSerializer, ProcessSerializer
from ..permissions import SuperuserFriendlyModelPermissions


class CustomerViewSet(viewsets.ModelViewSet):
    """客户视图集"""
    queryset = Customer.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]  # 使用超级用户友好的模型权限
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'contact_person', 'phone']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        根据用户权限过滤查询集：
        - 如果有 change_customer 权限，返回所有客户
        - 如果是业务员，只返回自己负责的客户
        - 如果有 view_customer 权限，返回所有客户（只读）
        """
        queryset = super().get_queryset()

        # 如果有编辑客户权限，返回所有客户
        if self.request.user.has_perm('workorder.change_customer'):
            return queryset.select_related('salesperson')

        # 如果是业务员，只返回自己负责的客户
        if self.request.user.groups.filter(name='业务员').exists():
            return queryset.filter(salesperson=self.request.user).select_related('salesperson')

        # 如果有查看客户权限，返回所有客户（只读）
        if self.request.user.has_perm('workorder.view_customer'):
            return queryset.select_related('salesperson')

        # 否则返回空查询集
        return queryset.none()



class DepartmentViewSet(viewsets.ModelViewSet):
    """部门视图集"""
    permission_classes = [SuperuserFriendlyModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'parent']
    search_fields = ['name', 'code']
    ordering_fields = ['sort_order', 'code']
    ordering = ['sort_order', 'code']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # 预加载关联数据，提高查询效率
        queryset = queryset.select_related('parent').prefetch_related('processes', 'children')
        return queryset



class ProcessViewSet(viewsets.ModelViewSet):
    """工序视图集"""
    permission_classes = [SuperuserFriendlyModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = Process.objects.all()
    serializer_class = ProcessSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_builtin']
    search_fields = ['name', 'code']
    ordering_fields = ['sort_order', 'code', 'created_at']
    ordering = ['sort_order', 'code']
    
    def destroy(self, request, *args, **kwargs):
        """删除工序，内置工序不可删除"""
        instance = self.get_object()
        if instance.is_builtin:
            return Response(
                {'error': '内置工序不可删除'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

