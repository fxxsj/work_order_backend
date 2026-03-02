"""
基础数据视图集

包含客户、部门、工序等基础数据的视图集。
"""

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.decorators import action
from workorder.response import APIResponse

from workorder.docs.base import (
    customer_docs,
    department_all_docs,
    department_docs,
    department_tree_docs,
    process_all_docs,
    process_docs,
)

from ..models.base import Customer, Department, Process
from ..serializers.base import CustomerSerializer, DepartmentSerializer, ProcessSerializer
from .base_viewsets import BaseViewSet


@customer_docs
class CustomerViewSet(BaseViewSet):
    """客户视图集"""

    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    search_fields = ["name", "contact_person", "phone"]
    ordering_fields = ["created_at", "name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """
        根据用户权限过滤查询集：
        - 如果有 change_customer 权限，返回所有客户
        - 如果是业务员，只返回自己负责的客户
        - 如果有 view_customer 权限，返回所有客户（只读）
        """
        queryset = super().get_queryset()

        # 如果有编辑客户权限，返回所有客户
        if self.request.user.has_perm("workorder.change_customer"):
            return queryset.select_related("salesperson")

        # 如果是业务员，只返回自己负责的客户
        if self.request.user.groups.filter(name="业务员").exists():
            return queryset.filter(salesperson=self.request.user).select_related(
                "salesperson"
            )

        # 如果有查看客户权限，返回所有客户（只读）
        if self.request.user.has_perm("workorder.view_customer"):
            return queryset.select_related("salesperson")

        # 否则返回空查询集
        return queryset.none()

    def destroy(self, request, *args, **kwargs):
        """删除客户

        检查：客户是否有关联的施工单
        """
        instance = self.get_object()

        # 检查是否有关联的施工单
        from ..models.core import WorkOrder

        if WorkOrder.objects.filter(customer=instance).exists():
            return APIResponse.error(
                "该客户有关联的施工单，不可删除",
                code=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)


@department_docs
class DepartmentViewSet(BaseViewSet):
    """部门视图集

    提供部门的 CRUD 操作、搜索、过滤和排序功能。
    """

    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filterset_fields = ["is_active", "parent"]
    search_fields = ["name", "code"]
    ordering_fields = ["sort_order", "code"]
    ordering = ["sort_order", "code"]

    def get_queryset(self):
        queryset = super().get_queryset()
        # 预加载关联数据，提高查询效率
        queryset = queryset.select_related("parent").prefetch_related(
            "processes", "children"
        )
        return queryset

    def destroy(self, request, *args, **kwargs):
        """删除部门

        检查：
            1. 有子部门的部门不可删除
            2. 有关联用户的部门不可删除（如果有）
        """
        instance = self.get_object()

        # 检查是否有子部门
        if instance.children.exists():
            return APIResponse.error(
                "该部门有子部门，请先删除子部门",
                code=status.HTTP_400_BAD_REQUEST,
            )

        # 检查是否有关联的施工单任务
        from ..models.core import WorkOrderTask

        if WorkOrderTask.objects.filter(assigned_department=instance).exists():
            return APIResponse.error(
                "该部门已被施工单任务使用，不可删除",
                code=status.HTTP_400_BAD_REQUEST,
            )

        if WorkOrderTask.objects.filter(work_order_process__department=instance).exists():
            return APIResponse.error(
                "该部门已被施工单任务使用，不可删除",
                code=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    @department_tree_docs
    def tree(self, request):
        """获取部门树结构

        返回按层级组织的部门树，便于前端展示。
        """
        cache_timeout = getattr(settings, "DICT_CACHE_TIMEOUT", 300)
        cache_key = "dict:departments:tree"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return APIResponse.success(data=cached_data)

        # 获取所有顶级部门（没有上级的部门）
        root_departments = self.get_queryset().filter(parent__isnull=True)

        def build_tree(department):
            """递归构建部门树"""
            serializer = self.get_serializer(department)
            data = serializer.data
            children = department.children.all()
            if children:
                data["children"] = [build_tree(child) for child in children]
            else:
                data["children"] = []
            return data

        tree_data = [build_tree(dept) for dept in root_departments]

        cache.set(cache_key, tree_data, timeout=cache_timeout)
        return APIResponse.success(data=tree_data)

    @action(detail=False, methods=["get"])
    @department_all_docs
    def all(self, request):
        """获取所有部门（简化版，用于下拉选择）

        返回所有启用的部门列表，不分页。
        """
        cache_timeout = getattr(settings, "DICT_CACHE_TIMEOUT", 300)
        is_active = request.query_params.get("is_active")
        if is_active is None:
            key_suffix = "any"
        else:
            key_suffix = "true" if is_active.lower() == "true" else "false"
        cache_key = f"dict:departments:all:{key_suffix}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return APIResponse.success(data=cached_data)

        queryset = self.get_queryset()

        # 可选：只返回启用的部门
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        cache.set(cache_key, data, timeout=cache_timeout)
        return APIResponse.success(data=data)


@process_docs
class ProcessViewSet(BaseViewSet):
    """工序视图集

    提供工序的 CRUD 操作、搜索、过滤和排序功能。
    """

    queryset = Process.objects.all()
    serializer_class = ProcessSerializer
    filterset_fields = ["is_active", "is_builtin", "task_generation_rule"]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["sort_order", "code", "created_at"]
    ordering = ["sort_order", "code"]

    @action(detail=False, methods=["get"])
    @process_all_docs
    def all(self, request):
        """获取所有工序（简化版，用于下拉选择）

        返回工序列表，不分页。
        """
        cache_timeout = getattr(settings, "DICT_CACHE_TIMEOUT", 300)
        is_active = request.query_params.get("is_active")
        if is_active is None:
            key_suffix = "any"
        else:
            key_suffix = "true" if is_active.lower() == "true" else "false"
        cache_key = f"dict:processes:all:{key_suffix}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return APIResponse.success(data=cached_data)

        queryset = self.get_queryset().order_by("sort_order", "code")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        cache.set(cache_key, data, timeout=cache_timeout)
        return APIResponse.success(data=data)

    def destroy(self, request, *args, **kwargs):
        """删除工序，内置工序和使用中的工序不可删除"""
        instance = self.get_object()

        if instance.is_builtin:
            return APIResponse.error(
                "内置工序不可删除",
                code=status.HTTP_400_BAD_REQUEST,
            )

        # 检查是否有施工单在使用此工序
        from ..models.core import WorkOrderProcess

        if WorkOrderProcess.objects.filter(process=instance).exists():
            return APIResponse.error(
                "该工序已被施工单使用，不可删除",
                code=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["post"])
    def batch_update_active(self, request):
        """批量更新工序启用状态"""
        ids = request.data.get("ids", [])
        is_active = request.data.get("is_active", True)

        if not ids:
            return APIResponse.error(
                "请提供要更新的工序ID列表",
                code=status.HTTP_400_BAD_REQUEST,
            )

        # 保护内置工序
        if is_active is False:
            builtin_count = Process.objects.filter(id__in=ids, is_builtin=True).count()

            if builtin_count > 0:
                return APIResponse.error(
                    f"不能禁用 {builtin_count} 个内置工序",
                    code=status.HTTP_400_BAD_REQUEST,
                )

        # 批量更新
        updated = Process.objects.filter(id__in=ids).update(is_active=is_active)

        return APIResponse.success(data={"updated_count": updated})
