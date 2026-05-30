from typing import TypeVar, Generic
from django.contrib.auth import get_user_model
from rest_framework import status
from django.utils import timezone
from workorder.services.service_errors import ServiceError

User = get_user_model()
T = TypeVar('T')

class ApprovalService(Generic[T]):
    """通用审核服务（仅用于4个核心审核模块）"""
    
    # 只包含需要审核的4个模块
    APPROVE_PERMISSION_MAP = {
        "workorder": "workorder.approve_workorder",
        "salesorder": "workorder.approve_salesorder",
        "purchaseorder": "workorder.approve_purchaseorder",
        "invoice": "workorder.approve_invoice",
    }
    
    SUBMIT_PERMISSION_MAP = {
        "workorder": "workorder.submit_workorder",
        "salesorder": "workorder.submit_salesorder",
        "purchaseorder": "workorder.submit_purchaseorder",
        "invoice": "workorder.submit_invoice",
    }
    
    def __init__(self, model_class: type[T]):
        self.model_class = model_class
        self.model_name = model_class._meta.model_name
    
    def get_approve_permission(self) -> str:
        """获取当前模型对应的审核权限"""
        return self.APPROVE_PERMISSION_MAP.get(self.model_name)
    
    def get_submit_permission(self) -> str:
        """获取当前模型对应的提交审核权限"""
        return self.SUBMIT_PERMISSION_MAP.get(self.model_name)
    
    def validate_approval_permission(self, user, obj) -> None:
        """验证用户是否有审核权限"""
        if user.is_superuser:
            return
        
        permission = self.get_approve_permission()
        if not permission:
            raise ServiceError(
                f"模型 {self.model_name} 不需要审核",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        if not user.has_perm(permission):
            raise ServiceError(
                "您没有审核权限",
                code=status.HTTP_403_FORBIDDEN,
            )
    
    def validate_submit_permission(self, user, obj) -> None:
        """验证用户是否有提交审核权限"""
        if user.is_superuser:
            return
        
        permission = self.get_submit_permission()
        if not permission:
            raise ServiceError(
                f"模型 {self.model_name} 不需要提交审核",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        if not user.has_perm(permission):
            raise ServiceError(
                "您没有提交审核权限",
                code=status.HTTP_403_FORBIDDEN,
            )
    
    def validate_status(self, obj, expected_status: str) -> None:
        """验证对象状态是否允许审核"""
        current_status = getattr(obj, 'approval_status', getattr(obj, 'status', None))
        if current_status != expected_status:
            raise ServiceError(
                f"当前状态不允许此操作（当前: {current_status}）",
                code=status.HTTP_400_BAD_REQUEST,
            )
    
    def approve(self, obj, user, comment: str = "") -> T:
        """审核通过"""
        self.validate_approval_permission(user, obj)
        self.validate_status(obj, "submitted")
        
        obj.approval_status = "approved"
        obj.approved_by = user
        obj.approved_at = timezone.now()
        obj.approval_comment = comment
        obj.save()
        
        self._log_approval(obj, user, "approve", comment)
        return obj
    
    def reject(self, obj, user, reason: str, comment: str = "") -> T:
        """审核拒绝"""
        self.validate_approval_permission(user, obj)
        self.validate_status(obj, "submitted")
        
        obj.approval_status = "rejected"
        obj.approved_by = user
        obj.approved_at = timezone.now()
        obj.approval_comment = comment or reason
        obj.save()
        
        self._log_approval(obj, user, "reject", reason)
        return obj
    
    def submit_for_approval(self, obj, user, comment: str = "", auto_approve: bool = False) -> T:
        """提交审核"""
        self.validate_submit_permission(user, obj)
        current_status = getattr(obj, 'approval_status', getattr(obj, 'status', None))
        if current_status not in ["draft", "rejected"]:
            raise ServiceError(
                f"当前状态不允许此操作（当前: {current_status}）",
                code=status.HTTP_400_BAD_REQUEST,
            )
        
        obj.approval_status = "submitted"
        if hasattr(obj, 'submitted_by'):
            obj.submitted_by = user
        if hasattr(obj, 'submitted_at'):
            obj.submitted_at = timezone.now()
        obj.save()
        
        self._log_approval(obj, user, "submit", comment)

        # 智能免审逻辑：如果请求了自动审核，并且用户拥有审核权限
        if auto_approve:
            permission = self.get_approve_permission()
            if user.is_superuser or (permission and user.has_perm(permission)):
                self.approve(obj, user, comment="系统自动审核通过（具有审核权限）")
                
        return obj
    
    def _log_approval(self, obj, user, action: str, comment: str) -> None:
        """记录审核日志"""
        pass
