"""
自定义权限类
用于处理特殊的权限需求
"""
from rest_framework import permissions


class IsStaffOrReadOnly(permissions.BasePermission):
    """
    自定义权限：只有 staff 用户可以修改，其他用户只能查看
    用于某些敏感操作
    """
    def has_permission(self, request, view):
        # 读取操作：所有已登录用户都可以
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # 写入操作：只有 staff 用户可以
        return request.user.is_authenticated and request.user.is_staff


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    自定义权限：只有对象的所有者可以修改
    用于用户只能修改自己创建的资源
    """
    def has_object_permission(self, request, view, obj):
        # 读取操作：所有已登录用户都可以
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # 写入操作：只有所有者可以
        return obj.created_by == request.user


class WorkOrderProcessPermission(permissions.BasePermission):
    """
    施工单工序权限：如果用户有编辑施工单的权限，就可以编辑其工序
    工序是施工单的一部分，逻辑上应该与施工单权限一致
    """
    def has_permission(self, request, view):
        # 检查用户是否已登录
        if not request.user.is_authenticated:
            return False
        
        # 读取操作：检查是否有查看施工单的权限
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm('workorder.view_workorder')
        
        # 写入操作：检查是否有编辑施工单的权限
        # 如果有编辑施工单的权限，就可以编辑其工序
        return request.user.has_perm('workorder.change_workorder')
    
    def has_object_permission(self, request, view, obj):
        """
        对象级权限检查：确保用户有权限编辑该工序所属的施工单
        """
        # 检查用户是否已登录
        if not request.user.is_authenticated:
            return False
        
        # 读取操作：检查是否有查看施工单的权限
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm('workorder.view_workorder')
        
        # 写入操作：检查是否有编辑该工序所属施工单的权限
        if hasattr(obj, 'work_order') and obj.work_order:
            # 检查是否有编辑该施工单的权限
            return request.user.has_perm('workorder.change_workorder')
        
        # 如果没有关联的施工单，检查是否有编辑施工单的权限
        return request.user.has_perm('workorder.change_workorder')


class WorkOrderMaterialPermission(permissions.BasePermission):
    """
    施工单物料权限：如果用户有编辑施工单的权限，就可以编辑其物料
    物料是施工单的一部分，逻辑上应该与施工单权限一致
    """
    def has_permission(self, request, view):
        # 检查用户是否已登录
        if not request.user.is_authenticated:
            return False
        
        # 读取操作：检查是否有查看施工单的权限
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm('workorder.view_workorder')
        
        # 写入操作：检查是否有编辑施工单的权限
        # 如果有编辑施工单的权限，就可以编辑其物料
        return request.user.has_perm('workorder.change_workorder')
    
    def has_object_permission(self, request, view, obj):
        """
        对象级权限检查：确保用户有权限编辑该物料所属的施工单
        """
        # 检查用户是否已登录
        if not request.user.is_authenticated:
            return False
        
        # 读取操作：检查是否有查看施工单的权限
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm('workorder.view_workorder')
        
        # 写入操作：检查是否有编辑该物料所属施工单的权限
        if hasattr(obj, 'work_order') and obj.work_order:
            # 检查是否有编辑该施工单的权限
            return request.user.has_perm('workorder.change_workorder')
        
        # 如果没有关联的施工单，检查是否有编辑施工单的权限
        return request.user.has_perm('workorder.change_workorder')

