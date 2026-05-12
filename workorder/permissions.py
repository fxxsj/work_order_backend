"""
自定义权限类
用于处理特殊的权限需求

P1 优化：使用缓存减少权限检查的数据库查询
"""

from rest_framework import permissions
from .permission_utils import PermissionCache, PermissionUtils


class SuperuserFriendlyModelPermissions(permissions.DjangoModelPermissions):
    """
    扩展 DjangoModelPermissions，明确处理 superuser

    虽然 DjangoModelPermissions 理论上会自动处理 superuser，
    但为了确保万无一失，我们显式检查 is_superuser
    """

    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [],
        "HEAD": [],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }

    def has_permission(self, request, view):
        # 超级用户拥有所有权限
        if request.user and request.user.is_superuser:
            return True

        # 其他用户使用 Django 模型权限检查
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        # 超级用户拥有所有权限
        if request.user and request.user.is_superuser:
            return True

        # DjangoModelPermissions 默认不检查对象级权限
        # 它只在 queryset 被过滤时才检查对象权限
        # 所以对于全局 queryset，我们直接返回 True
        return True


class CustomerDataPermission(permissions.BasePermission):
    """
    客户数据权限。

    施工单新建/编辑页会读取客户列表，因此允许拥有施工单读写权限的用户
    以只读方式访问客户数据；客户增删改仍沿用客户模型权限控制。
    """

    _customer_read_permissions = (
        "workorder.view_customer",
        "workorder.change_customer",
    )
    _work_order_read_permissions = (
        "workorder.view_workorder",
        "workorder.add_workorder",
        "workorder.change_workorder",
    )

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if request.method in permissions.SAFE_METHODS:
            return PermissionUtils.has_any_permission(
                request.user,
                self._customer_read_permissions + self._work_order_read_permissions,
            )

        if request.method == "POST":
            return request.user.has_perm("workorder.add_customer")

        if request.method in ("PUT", "PATCH"):
            return request.user.has_perm("workorder.change_customer")

        if request.method == "DELETE":
            return request.user.has_perm("workorder.delete_customer")

        return False

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class WorkOrderSupportingDataPermission(permissions.BasePermission):
    """
    施工单依赖基础数据权限。

    施工单表单需要读取图稿、刀模、烫金版、压凸版等基础资产，
    因此允许拥有施工单读写权限的用户只读访问这些资源。
    """

    _work_order_permissions = (
        "workorder.view_workorder",
        "workorder.add_workorder",
        "workorder.change_workorder",
    )

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        model = getattr(getattr(view, "queryset", None), "model", None)
        if model is None:
            return False

        app_label = model._meta.app_label
        model_name = model._meta.model_name

        if request.method in permissions.SAFE_METHODS:
            if PermissionUtils.has_any_permission(
                request.user,
                (
                    f"{app_label}.view_{model_name}",
                    f"{app_label}.change_{model_name}",
                ),
            ):
                return True
            return PermissionUtils.has_any_permission(
                request.user,
                self._work_order_permissions,
            )

        method_to_action = {
            "POST": "add",
            "PUT": "change",
            "PATCH": "change",
            "DELETE": "delete",
        }
        action = method_to_action.get(request.method)
        if action is None:
            return False
        return request.user.has_perm(f"{app_label}.{action}_{model_name}")

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


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


class WorkOrderAssetPermission(permissions.BasePermission):
    """
    施工单关联资产（如工序、物料）的通用权限。

    核心逻辑：
    - 如果用户对施工单有读取权限，就能读取关联资产。
    - 如果用户对施工单有修改权限，就能修改关联资产。
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm("workorder.view_workorder")
        return request.user.has_perm("workorder.change_workorder")

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm("workorder.view_workorder")

        # 对于写入操作，只要用户有修改工单的通用权限即可。
        # 对象级检查仅确认与工单的关联，权限判断是统一的。
        return request.user.has_perm("workorder.change_workorder")


class WorkOrderProcessPermission(WorkOrderAssetPermission):
    """
    施工单工序权限：如果用户有编辑施工单的权限，就可以编辑其工序。
    工序是施工单的一部分，逻辑上应该与施工单权限一致，因此继承通用资产权限。
    """

    pass


class WorkOrderMaterialPermission(WorkOrderAssetPermission):
    """
    施工单物料权限：如果用户有编辑施工单的权限，就可以编辑其物料。
    物料是施工单的一部分，逻辑上应该与施工单权限一致，因此继承通用资产权限。
    """

    pass


class WorkOrderProductPermission(WorkOrderAssetPermission):
    """
    施工单产品权限：施工单产品是施工单的一部分，沿用施工单读写权限。
    """

    pass


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

        # 超级用户拥有所有权限
        if request.user.is_superuser:
            return True

        # 读取操作：检查是否有查看施工单的权限
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm("workorder.view_workorder")

        # 写入操作：允许有查看权限的用户访问，具体权限由 has_object_permission 检查
        # 这样可以让操作员通过 update_quantity 等操作更新自己的任务
        return request.user.has_perm("workorder.view_workorder")

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
            if request.user.is_superuser or request.user.has_perm(
                "workorder.view_workorder"
            ):
                return True

            # 操作员只能查看自己分派的任务
            if obj.assigned_operator == request.user:
                return True

            # 生产主管可以查看本部门的任务
            if obj.assigned_department:
                # P1 优化: 使用缓存检查用户是否属于该部门
                if PermissionCache.is_user_in_department(
                    request.user, obj.assigned_department.id
                ):
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
            if PermissionCache.is_user_in_department(
                request.user, obj.assigned_department.id
            ):
                # 检查是否有 change_workorder 权限（生产主管）
                if request.user.has_perm("workorder.change_workorder"):
                    return True

        # 施工单创建人可以操作自己创建的施工单的任务
        if obj.work_order_process.work_order.created_by == request.user:
            return True

        # 跨部门操作需要特殊权限
        if request.user.has_perm("workorder.change_workorder"):
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

        # 超级用户拥有所有权限
        if request.user.is_superuser:
            return True

        # 读取操作：检查是否有查看施工单的权限
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm("workorder.view_workorder")

        if request.method == "DELETE":
            return request.user.has_perm("workorder.delete_workorder")

        # 写入操作：检查是否有编辑施工单的权限
        return request.user.has_perm("workorder.change_workorder")

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
            if hasattr(obj, "customer") and obj.customer:
                if obj.customer.salesperson == request.user:
                    return True

            # 生产主管可以查看本部门有任务的施工单
            if request.user.has_perm("workorder.change_workorder"):
                # 检查是否有本部门的任务
                user_departments = (
                    request.user.profile.departments.all()
                    if hasattr(request.user, "profile")
                    else []
                )
                if user_departments:
                    # 检查施工单是否有任务分派到用户部门
                    from .models import WorkOrderTask

                    has_department_task = WorkOrderTask.objects.filter(
                        work_order_process__work_order=obj,
                        assigned_department__in=user_departments,
                    ).exists()
                    if has_department_task:
                        return True

            # 注意：不再有 view_workorder 全局 fallback
            # 数据可见性完全由创建人/业务员/部门作用域决定
            return False

        if request.method == "DELETE":
            return request.user.has_perm("workorder.delete_workorder")

        # 写入操作：更严格的权限控制
        # 施工单创建人可以编辑自己创建的施工单（在审核前）
        if obj.created_by == request.user:
            # 如果已审核，需要特殊权限
            if obj.approval_status == "approved":
                return request.user.has_perm("workorder.change_workorder")
            return True

        # 有 change_workorder 权限的用户可以编辑
        if request.user.has_perm("workorder.change_workorder"):
            return True

        return False
