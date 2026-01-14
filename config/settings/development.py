"""
Development settings for Vehicle Insurance Information System.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG', default=True)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# Optional: allow SQLite locally to simplify onboarding
USE_SQLITE = env.bool('USE_SQLITE', default=False)
if USE_SQLITE:
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }

# Development-specific apps
INSTALLED_APPS += [
    'debug_toolbar',
]

# Debug toolbar middleware
MIDDLEWARE += [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
]

# Debug toolbar configuration
INTERNAL_IPS = [
    '127.0.0.1',
]

# Show toolbar only for superusers to avoid confusing regular users during demos
def show_toolbar(request):
    try:
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and user.is_superuser)
    except Exception:
        return False

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': 'config.settings.development.show_toolbar',
}

# Disable HTTPS-only cookies in development
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Use in-memory cache in development so features depending on cache (e.g.,
# login rate limiting) work without a running Redis instance.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'vehicle_insurance_dev_local_cache',
        'TIMEOUT': 300,
        'KEY_PREFIX': 'vehicle_insurance_dev',
    },
    'sessions': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'vehicle_insurance_dev_sessions',
        'TIMEOUT': 60 * 60 * 8,  # 8 hours to match session age
        'KEY_PREFIX': 'sessions',
    },
}

# Email backend for development (console output)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable some security features for easier development
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# CORS settings for development (allow localhost)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True

# Make password hashers faster for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Show SQL queries in console (useful for debugging, remove if too verbose)
# LOGGING['loggers']['django.db.backends'] = {
#     'level': 'DEBUG',
#     'handlers': ['console'],
# }
