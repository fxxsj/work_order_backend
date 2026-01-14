# 查询优化配置

# 1. 数据库索引建议
# 运行: python manage.py makemigrations workorder --empty
# 然后参考 add_indexes.py 创建索引迁移

# 2. 查询优化配置
# 在 settings.py 中添加:

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            # SQLite 优化
            'timeout': 20,
            'check_same_thread': False,
        },
        # PostgreSQL 优化（如果使用 PostgreSQL）
        # 'ENGINE': 'django.db.backends.postgresql',
        # 'HOST': 'localhost',
        # 'PORT': '5432',
        # 'USER': 'postgres',
        # 'PASSWORD': 'password',
        # 'NAME': 'workorder',
        # 'OPTIONS': {
        #     'connect_timeout': 10,
        #     'options': '-c statement_timeout=30000',
        # },
    }
}

# REST_FRAMEWORK 分页配置
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'MAX_PAGE_SIZE': 100,  # 限制最大页大小
    # 或使用游标分页（更高效）
    # 'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.CursorPagination',
    # 'PAGE_SIZE': 20,
}

# 3. 缓存配置（如果使用 Redis）
# CACHES = {
#     'default': {
#         'BACKEND': 'django.core.cache.backends.redis.RedisCache',
#         'LOCATION': 'redis://127.0.0.1:6379/1',
#         'OPTIONS': {
#             'CLIENT_CLASS': 'django_redis.client.DefaultClient',
#         },
#         'KEY_PREFIX': 'workorder',
#         'TIMEOUT': 300,
#     }
# }

# 4. 查询优化装饰器
from functools import wraps
from django.db import connection, reset_queries
from django.conf import settings
import time
import logging

logger = logging.getLogger(__name__)

def query_debug(func):
    """查询调试装饰器 - 记录查询数量和执行时间"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if settings.DEBUG:
            reset_queries()
            start_time = time.time()

        result = func(*args, **kwargs)

        if settings.DEBUG:
            end_time = time.time()
            queries = len(connection.queries)
            logger.info(
                f"函数 {func.__name__} 执行了 {queries} 个查询, "
                f"耗时 {end_time - start_time:.3f}秒"
            )

            # 记录慢查询
            if end_time - start_time > 1.0:
                logger.warning(f"慢查询检测: {func.__name__} 耗时 {end_time - start_time:.3f}秒")

        return result
    return wrapper


def select_related_fields(*fields):
    """
    动态 select_related 装饰器

    使用:
    @select_related_fields('customer', 'created_by')
    def my_view(self, request):
        queryset = self.get_queryset()
        ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            queryset = self.get_queryset()
            if fields:
                queryset = queryset.select_related(*fields)
            self.queryset = queryset
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def prefetch_related_fields(*fields):
    """
    动态 prefetch_related 装饰器

    使用:
    @prefetch_related_fields('order_processes__process', 'products__product')
    def my_view(self, request):
        queryset = self.get_queryset()
        ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            queryset = self.get_queryset()
            if fields:
                queryset = queryset.prefetch_related(*fields)
            self.queryset = queryset
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


# 5. 查询分析工具
class QueryAnalyzer:
    """查询分析器"""

    @staticmethod
    def analyze_queryset(queryset, name="Query"):
        """分析查询集并打印优化建议"""
        if not settings.DEBUG:
            return

        from django.db import connection
        from django.db.models import QuerySet

        if not isinstance(queryset, QuerySet):
            return

        # 强制执行查询
        list(queryset)

        queries = connection.queries
        total_time = sum(float(q['time']) for q in queries)
        count = len(queries)

        logger.info(f"{name} 查询分析:")
        logger.info(f"  总查询数: {count}")
        logger.info(f"  总耗时: {total_time:.3f}秒")
        logger.info(f"  平均耗时: {total_time / count:.3f}秒/查询")

        # 检测 N+1 问题
        if count > 10:
            logger.warning(f"  ⚠️  可能存在 N+1 问题：查询数过多 ({count} 个)")

        # 检测慢查询
        if total_time > 1.0:
            logger.warning(f"  ⚠️  慢查询：总耗时过长 ({total_time:.3f}秒)")

        # 打印前 5 个最慢的查询
        sorted_queries = sorted(queries, key=lambda x: float(x['time']), reverse=True)[:5]
        logger.info(f"  最慢的 5 个查询:")
        for i, q in enumerate(sorted_queries, 1):
            logger.info(f"    {i}. {q['time']}秒 - {q['sql'][:100]}...")
