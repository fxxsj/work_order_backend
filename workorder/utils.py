"""
工具函数
"""
from django.contrib.auth.models import User


def is_salesperson(user):
    """
    判断用户是否为业务员
    
    Args:
        user: User 实例或用户对象
        
    Returns:
        bool: 如果用户属于"业务员"组，返回 True，否则返回 False
    """
    if not user or not user.is_authenticated:
        return False
    
    # 如果传入的是用户ID，获取用户对象
    if isinstance(user, int):
        try:
            user = User.objects.get(pk=user)
        except User.DoesNotExist:
            return False
    
    return user.groups.filter(name='业务员').exists()


def get_user_role(user):
    """
    获取用户角色
    
    Args:
        user: User 实例
        
    Returns:
        str: 用户角色名称，如果用户属于多个组，返回第一个组的名称
    """
    if not user or not user.is_authenticated:
        return None
    
    groups = user.groups.all()
    if groups.exists():
        return groups.first().name
    return None

