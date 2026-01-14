"""
Production settings for Vehicle Insurance Information System.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# Security settings for production
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# CORS settings for production (configure based on your needs)
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
CORS_ALLOW_CREDENTIALS = True

# Trust Render domain(s) for CSRF if provided
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# Email configuration for production
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@vehicle-insurance.com')

# Adjust logging for production
LOGGING['handlers']['file']['filename'] = '/var/log/vehicle_insurance/app.log'

# Remove debug_toolbar from installed apps (if somehow included)
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'debug_toolbar']
MIDDLEWARE = [mw for mw in MIDDLEWARE if 'debug_toolbar' not in mw]

# Production cache configuration (override defaults to avoid localhost Redis)
# Provide Redis URLs via environment variables:
# - CACHE_DEFAULT_URL (fallback to REDIS_URL)
# - CACHE_SESSIONS_URL (fallback to REDIS_URL)
# - CACHE_TENANT_URL (fallback to REDIS_URL)
_CACHE_DEFAULT_URL = env('CACHE_DEFAULT_URL', default=env('REDIS_URL', default='redis://localhost:6379/0'))
_CACHE_SESSIONS_URL = env('CACHE_SESSIONS_URL', default=env('REDIS_URL', default='redis://localhost:6379/0'))
_CACHE_TENANT_URL = env('CACHE_TENANT_URL', default=env('REDIS_URL', default='redis://localhost:6379/0'))

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': _CACHE_DEFAULT_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'vehicle_insurance',
        'TIMEOUT': 300,
        'VERSION': 1,
    },
    'sessions': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': _CACHE_SESSIONS_URL,
        'TIMEOUT': 28800,
        'KEY_PREFIX': 'sessions',
    },
    'tenant_data': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': _CACHE_TENANT_URL,
        'TIMEOUT': 3600,
        'KEY_PREFIX': 'tenant',
    },
}
