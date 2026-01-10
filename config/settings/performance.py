"""
Performance optimization settings for Vehicle Insurance System.
Implements caching, database optimization, and efficient resource management.
"""

# Database Performance
DATABASE_PERFORMANCE = {
    'CONN_MAX_AGE': 600,  # 10 minutes connection pooling
    'ATOMIC_REQUESTS': True,
    'OPTIONS': {
        'MAX_CONNS': 20,
        'CONN_HEALTH_CHECKS': True,
    }
}

# Cache Configuration (Redis-based)
CACHE_PERFORMANCE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://localhost:6379/0',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
        },
        'KEY_PREFIX': 'vehicle_insurance',
        'TIMEOUT': 300,  # 5 minutes default
        'VERSION': 1,
    },
    'sessions': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://localhost:6379/1',
        'TIMEOUT': 28800,  # 8 hours
        'KEY_PREFIX': 'sessions',
    },
    'tenant_data': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://localhost:6379/2',
        'TIMEOUT': 3600,  # 1 hour
        'KEY_PREFIX': 'tenant',
    }
}

# Session Performance
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'

# Static Files Performance
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True

# Template Performance
TEMPLATE_PERFORMANCE = {
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'apps.tenants.context_processors.tenant_context',
            'apps.super_admin.context_processors.platform_config',
        ],
        'loaders': [
            ('django.template.loaders.cached.Loader', [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ]),
        ],
    },
}

# Query Optimization
QUERY_OPTIMIZATION = {
    'SELECT_RELATED_DEPTH': 2,
    'PREFETCH_RELATED_LOOKUPS': True,
    'USE_INDEXES': True,
}

# Celery Performance
CELERY_PERFORMANCE = {
    'BROKER_CONNECTION_RETRY_ON_STARTUP': True,
    'TASK_ACKS_LATE': True,
    'WORKER_PREFETCH_MULTIPLIER': 1,
    'TASK_COMPRESSION': 'gzip',
    'RESULT_COMPRESSION': 'gzip',
    'TASK_ROUTES': {
        'apps.notifications.tasks.send_expiry_reminders': {'queue': 'notifications'},
        'apps.notifications.tasks.refresh_dashboard_metrics': {'queue': 'metrics'},
        'apps.reports.tasks.generate_report': {'queue': 'reports'},
    },
    'WORKER_CONCURRENCY': 4,
    'TASK_TIME_LIMIT': 1800,  # 30 minutes
    'TASK_SOFT_TIME_LIMIT': 1500,  # 25 minutes
}

# Pagination Performance
PAGINATION_SETTINGS = {
    'DEFAULT_PAGE_SIZE': 25,
    'MAX_PAGE_SIZE': 100,
    'PAGE_SIZE_QUERY_PARAM': 'page_size',
}

# File Upload Performance
FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]

# Logging Performance
LOGGING_PERFORMANCE = {
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        }
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/app.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'json',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/error.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
}