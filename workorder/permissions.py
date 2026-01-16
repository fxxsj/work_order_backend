"""
自定义权限类
用于处理特殊的权限需求

P1 优化：使用缓存减少权限检查的数据库查询
"""
from rest_framework import permissions
from .permission_utils import PermissionCache


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


class WorkOrderTaskPermission(permissions.BasePermission):
    """
    任务操作权限：细粒度权限控制
    
    规则：
    1. 操作员只能更新自己分派的任务
    2. 生产主管可以更新本部门的所有任务
    3. 管理员可以更新所有任务
    4. 跨部门操作需要特殊权限（change_workorder）
    """
    def has_permission(self, request, view):
        # 检查用户是否已登录
        if not request.user.is_authenticated:
            return False
        
        # 读取操作：检查是否有查看施工单的权限
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm('workorder.view_workorder')
        
        # 写入操作：检查是否有编辑施工单的权限
        return request.user.has_perm('workorder.change_workorder')
    
    def has_object_permission(self, request, view, obj):
        """
        对象级权限检查：基于任务分派和部门进行权限控制
        """
        # 检查用户是否已登录
        if not request.user.is_authenticated:
            return False
        
        # 读取操作：检查数据权限
        if request.method in permissions.SAFE_METHODS:
            # 管理员可以查看所有任务
            if request.user.is_superuser or request.user.has_perm('workorder.view_workorder'):
                return True
            
            # 操作员只能查看自己分派的任务
            if obj.assigned_operator == request.user:
                return True
            
            # 生产主管可以查看本部门的任务
            if obj.assigned_department:
                # P1 优化: 使用缓存检查用户是否属于该部门
                if PermissionCache.is_user_in_department(request.user, obj.assigned_department.id):
                    return True
            
            # 施工单创建人可以查看自己创建的施工单的任务
            if obj.work_order_process.work_order.created_by == request.user:
                return True
            
            return False
        
        # 写入操作：更严格的权限控制
        # 管理员可以操作所有任务
        if request.user.is_superuser:
            return True
        
        # 操作员只能更新自己分派的任务
        if obj.assigned_operator == request.user:
            return True
        
        # 生产主管可以更新本部门的所有任务
        if obj.assigned_department:
            # P1 优化: 使用缓存检查用户是否属于该部门
            if PermissionCache.is_user_in_department(request.user, obj.assigned_department.id):
                # 检查是否有 change_workorder 权限（生产主管）
                if request.user.has_perm('workorder.change_workorder'):
                    return True
        
        # 施工单创建人可以操作自己创建的施工单的任务
        if obj.work_order_process.work_order.created_by == request.user:
            return True
        
        # 跨部门操作需要特殊权限
        if request.user.has_perm('workorder.change_workorder'):
            # 检查是否是跨部门操作
            if obj.assigned_department:
                # P1 优化: 使用缓存检查跨部门操作
                user_departments = PermissionCache.get_user_departments(request.user)
                if obj.assigned_department.id not in user_departments:
                    # 跨部门操作，需要特殊权限（这里允许有 change_workorder 权限的用户）
                    return True
        
        return False


class WorkOrderDataPermission(permissions.BasePermission):
    """
    施工单数据权限：基于数据所有权的权限控制
    
    规则：
    1. 只能查看自己负责的施工单（业务员）
    2. 管理员可以查看所有数据
    3. 生产主管可以查看本部门的任务相关的施工单
    """
    def has_permission(self, request, view):
        # 检查用户是否已登录
        if not request.user.is_authenticated:
            return False
        
        # 读取操作：检查是否有查看施工单的权限
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm('workorder.view_workorder')
        
        # 写入操作：检查是否有编辑施工单的权限
        return request.user.has_perm('workorder.change_workorder')
    
    def has_object_permission(self, request, view, obj):
        """
        对象级权限检查：基于数据所有权进行权限控制
        """
        # 检查用户是否已登录
        if not request.user.is_authenticated:
            return False
        
        # 管理员可以查看所有数据
        if request.user.is_superuser:
            return True
        
        # 读取操作：数据权限
        if request.method in permissions.SAFE_METHODS:
            # 施工单创建人可以查看自己创建的施工单
            if obj.created_by == request.user:
                return True
            
            # 业务员只能查看自己负责的客户的施工单
            if hasattr(obj, 'customer') and obj.customer:
                if obj.customer.salesperson == request.user:
                    return True
            
            # 生产主管可以查看本部门有任务的施工单
            if request.user.has_perm('workorder.change_workorder'):
                # 检查是否有本部门的任务
                user_departments = request.user.profile.departments.all() if hasattr(request.user, 'profile') else []
                if user_departments:
                    # 检查施工单是否有任务分派到用户部门
                    from .models import WorkOrderTask
                    has_department_task = WorkOrderTask.objects.filter(
                        work_order_process__work_order=obj,
                        assigned_department__in=user_departments
                    ).exists()
                    if has_department_task:
                        return True
            
            # 有 view_workorder 权限的用户可以查看所有施工单（管理员等）
            if request.user.has_perm('workorder.view_workorder'):
                return True
            
            return False
        
        # 写入操作：更严格的权限控制
        # 施工单创建人可以编辑自己创建的施工单（在审核前）
        if obj.created_by == request.user:
            # 如果已审核，需要特殊权限
            if obj.approval_status == 'approved':
                return request.user.has_perm('workorder.change_workorder')
            return True
        
        # 有 change_workorder 权限的用户可以编辑
        if request.user.has_perm('workorder.change_workorder'):
            return True
        
        return False

