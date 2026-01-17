"""
P1 优化: 缓存服务模块
提供缓存装饰器和缓存工具函数，用于提升数据库查询性能
"""
from django.core.cache import cache
from django.conf import settings
import json
import hashlib
from functools import wraps
from typing import Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)


def cache_result(timeout: int = None, key_prefix: str = '') -> Callable:
    """
    缓存函数结果的装饰器
    
    Args:
        timeout: 缓存超时时间（秒），默认使用中等超时
        key_prefix: 缓存键前缀
    
    Usage:
        @cache_result(timeout=300, key_prefix='user_')
        def get_user_profile(user_id):
            # 数据库查询操作
            return user_profile
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 生成缓存键
            cache_key = _generate_cache_key(func, args, kwargs, key_prefix)
            
            # 尝试从缓存获取
            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return result
            
            # 缓存未命中，执行函数
            try:
                result = func(*args, **kwargs)
                # 设置缓存
                if timeout is None:
                    timeout = settings.CACHE_TIMEOUTS['MEDIUM']
                cache.set(cache_key, result, timeout)
                logger.debug(f"Cache set for key: {cache_key}, timeout: {timeout}")
                return result
            except Exception as e:
                logger.error(f"Error in cached function {func.__name__}: {e}")
                # 缓存出错时直接执行函数
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def cache_queryset(timeout: int = None, key_prefix: str = '') -> Callable:
    """
    缓存查询集的装饰器，专门用于Django QuerySet
    
    Args:
        timeout: 缓存超时时间（秒）
        key_prefix: 缓存键前缀
    
    Usage:
        @cache_queryset(timeout=600, key_prefix='workorder_list_')
        def get_workorder_list(filters):
            return WorkOrder.objects.filter(**filters)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 生成缓存键
            cache_key = _generate_cache_key(func, args, kwargs, key_prefix)
            
            # 尝试从缓存获取
            cached_ids = cache.get(cache_key)
            if cached_ids is not None:
                logger.debug(f"QuerySet cache hit for key: {cache_key}")
                # 从缓存获取ID列表，重新查询以确保数据新鲜度
                model_class = _get_model_from_func(func)
                return model_class.objects.filter(id__in=cached_ids)
            
            # 缓存未命中，执行查询
            try:
                queryset = func(*args, **kwargs)
                # 获取ID列表用于缓存
                ids = list(queryset.values_list('id', flat=True))
                
                # 设置缓存
                if timeout is None:
                    timeout = settings.CACHE_TIMEOUTS['MEDIUM']
                cache.set(cache_key, ids, timeout)
                logger.debug(f"QuerySet cache set for key: {cache_key}, count: {len(ids)}")
                return queryset
            except Exception as e:
                logger.error(f"Error in cached queryset {func.__name__}: {e}")
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def invalidate_cache_pattern(pattern: str) -> None:
    """
    根据模式使缓存失效
    
    Args:
        pattern: 缓存键模式（支持通配符）
    """
    try:
        # 获取所有缓存键
        cache_keys = cache._cache.get_client().keys(f"*{pattern}*")
        if cache_keys:
            # 删除匹配的键
            cache.delete_many(cache_keys)
            logger.info(f"Invalidated {len(cache_keys)} cache keys matching pattern: {pattern}")
    except Exception as e:
        logger.error(f"Error invalidating cache pattern {pattern}: {e}")


def invalidate_cache_keys(keys: list) -> None:
    """
    使指定的缓存键失效
    
    Args:
        keys: 要失效的缓存键列表
    """
    try:
        cache.delete_many(keys)
        logger.info(f"Invalidated cache keys: {keys}")
    except Exception as e:
        logger.error(f"Error invalidating cache keys {keys}: {e}")


def get_cached_or_none(key: str, default: Any = None) -> Any:
    """
    获取缓存值，如果不存在则返回默认值
    
    Args:
        key: 缓存键
        default: 默认值
    
    Returns:
        缓存的值或默认值
    """
    try:
        value = cache.get(key)
        return value if value is not None else default
    except Exception as e:
        logger.error(f"Error getting cache value for key {key}: {e}")
        return default


def set_cache_with_timeout(key: str, value: Any, timeout_name: str = 'MEDIUM') -> None:
    """
    设置缓存值，使用预定义的超时时间
    
    Args:
        key: 缓存键
        value: 要缓存的值
        timeout_name: 超时时间名称（SHORT, MEDIUM, LONG, HOUR, DAY）
    """
    try:
        timeout = settings.CACHE_TIMEOUTS.get(timeout_name, settings.CACHE_TIMEOUTS['MEDIUM'])
        cache.set(key, value, timeout)
        logger.debug(f"Set cache key {key} with timeout {timeout_name} ({timeout}s)")
    except Exception as e:
        logger.error(f"Error setting cache value for key {key}: {e}")


def _generate_cache_key(func: Callable, args: tuple, kwargs: dict, prefix: str) -> str:
    """
    生成缓存键
    
    Args:
        func: 被装饰的函数
        args: 函数位置参数
        kwargs: 函数关键字参数
        prefix: 键前缀
    
    Returns:
        生成的缓存键
    """
    # 生成参数的哈希值
    args_str = str(args) + str(sorted(kwargs.items()))
    args_hash = hashlib.md5(args_str.encode('utf-8')).hexdigest()[:8]
    
    # 组合缓存键
    function_name = func.__name__
    cache_key = f"{settings.CACHE_KEY_PREFIX}:{prefix}{function_name}:{args_hash}"
    
    return cache_key


def _get_model_from_func(func: Callable) -> Optional[Any]:
    """
    从函数中推断模型类（简单实现）
    
    Args:
        func: 被装饰的函数
    
    Returns:
        模型类或None
    """
    # 这里可以根据实际需要实现更复杂的逻辑
    # 例如通过函数名或源代码分析来推断
    try:
        # 简单实现：假设函数名包含模型名
        func_name = func.__name__
        if 'workorder' in func_name.lower():
            from workorder.models.core import WorkOrder
            return WorkOrder
        elif 'user' in func_name.lower():
            from django.contrib.auth.models import User
            return User
        # 可以添加更多模型的映射
    except ImportError:
        pass
    return None


class CacheManager:
    """
    缓存管理器，提供更高级的缓存操作
    """
    
    @staticmethod
    def cache_user_data(user_id: int, data_key: str, data: Any, timeout: int = None) -> None:
        """缓存用户相关数据"""
        cache_key = f"user_data:{user_id}:{data_key}"
        if timeout is None:
            timeout = settings.CACHE_TIMEOUTS['HOUR']
        cache.set(cache_key, data, timeout)
    
    @staticmethod
    def get_user_data(user_id: int, data_key: str, default: Any = None) -> Any:
        """获取用户缓存数据"""
        cache_key = f"user_data:{user_id}:{data_key}"
        return get_cached_or_none(cache_key, default)
    
    @staticmethod
    def invalidate_user_cache(user_id: int) -> None:
        """使用户缓存失效"""
        invalidate_cache_pattern(f"user_data:{user_id}:")
    
    @staticmethod
    def cache_workorder_data(workorder_id: int, data_key: str, data: Any, timeout: int = None) -> None:
        """缓存施工单相关数据"""
        cache_key = f"workorder_data:{workorder_id}:{data_key}"
        if timeout is None:
            timeout = settings.CACHE_TIMEOUTS['MEDIUM']
        cache.set(cache_key, data, timeout)
    
    @staticmethod
    def get_workorder_data(workorder_id: int, data_key: str, default: Any = None) -> Any:
        """获取施工单缓存数据"""
        cache_key = f"workorder_data:{workorder_id}:{data_key}"
        return get_cached_or_none(cache_key, default)
    
    @staticmethod
    def invalidate_workorder_cache(workorder_id: int) -> None:
        """使施工单缓存失效"""
        invalidate_cache_pattern(f"workorder_data:{workorder_id}:")
    
    @staticmethod
    def cache_permissions(user_id: int, permissions: list, timeout: int = None) -> None:
        """缓存用户权限"""
        cache_key = f"user_permissions:{user_id}"
        if timeout is None:
            timeout = settings.CACHE_TIMEOUTS['HOUR']
        cache.set(cache_key, permissions, timeout)
    
    @staticmethod
    def get_permissions(user_id: int, default: list = None) -> Any:
        """获取用户权限缓存"""
        cache_key = f"user_permissions:{user_id}"
        return get_cached_or_none(cache_key, default or [])