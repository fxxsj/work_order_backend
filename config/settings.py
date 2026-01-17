"""
Django settings for work order tracking system.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# 安全配置 - 从环境变量读取
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    import warnings
    warnings.warn("SECRET_KEY 环境变量未设置，使用不安全的默认值。请在 .env 文件中配置。")
    SECRET_KEY = 'django-insecure-fallback-key-for-development-only'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# 允许的主机
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')
if not ALLOWED_HOSTS or ALLOWED_HOSTS == ['']:
    # 开发环境默认值
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party apps
    'rest_framework',
    'rest_framework.authtoken',  # 添加 Token 认证支持
    'corsheaders',
    'django_filters',
    # Local apps
    'workorder',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

# 数据库配置 - 支持从环境变量读取
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# 如果设置了 PostgreSQL 环境变量（如 CI 环境），则使用 PostgreSQL
if os.environ.get('POSTGRES_DB'):
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'test_workorder'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS settings - 从环境变量读取
_cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if _cors_origins:
    CORS_ALLOWED_ORIGINS = _cors_origins.split(',')
else:
    # 开发环境默认值
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
    ]

CORS_ALLOW_CREDENTIALS = True

# CSRF settings - 从环境变量读取
_csrf_origins = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if _csrf_origins:
    CSRF_TRUSTED_ORIGINS = _csrf_origins.split(',')
else:
    # 开发环境默认值（注意：不能包含端口号）
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost",
        "http://127.0.0.1",
    ]

# 生产环境安全设置
if not DEBUG:
    # HTTPS 设置
    SECURE_SSL_REDIRECT = False  # 设为 True 前确保已配置 HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HSTS 设置
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # 其他安全设置
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # 'rest_framework.authentication.SessionAuthentication',  # 暂时禁用，避免 CSRF 冲突
        'rest_framework.authentication.TokenAuthentication',  # 只使用 Token 认证
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',  # 认证用户可读写，未认证用户只读
    ],
    # P1 优化: 添加速率限制配置
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',      # 匿名用户每小时最多 100 次请求
        'user': '1000/hour',     # 认证用户每小时最多 1000 次请求
        'approval': '10/hour',   # 审核操作每小时最多 10 次
        'export': '20/hour',     # 导出操作每小时最多 20 次
    },
}

# Session settings
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 86400  # 24 hours

# Logging settings (P1 优化：完善的日志系统)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'detailed': {
            'format': '{levelname} {asctime} {module} {funcName} {lineno:d} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'console_debug': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
            'filters': ['require_debug_true'],
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/django.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'file_error': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/django_error.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'django.db.backends': {
            'handlers': ['console_debug'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['file_error'],
            'level': 'ERROR',
            'propagate': False,
        },
        'workorder': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
    },
}

# 确保日志目录存在
import os
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)
