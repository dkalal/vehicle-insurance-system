from django.http import HttpResponse
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin

from .models import PlatformConfig


class MaintenanceModeMiddleware(MiddlewareMixin):
    """
    If platform maintenance is ON, block non-super-admin requests with HTTP 503,
    except for a small allowlist (health check, login/logout, static, admin).
    Super Admin is always allowed for platform administration.
    """

    ALLOW_NAMESPACES = {
        'admin',
        'accounts',
        'super_admin',
    }

    ALLOW_PATH_PREFIXES = (
        '/static/',
        '/health',
        '/__debug__/',
    )

    def process_request(self, request):
        cfg = PlatformConfig.get_solo()
        if not cfg.maintenance_mode:
            return None

        # Allow super admin
        user = getattr(request, 'user', None)
        if user and getattr(user, 'is_super_admin', False):
            return None

        # Allow allowlisted paths
        path = request.path or ''
        if any(path.startswith(p) for p in self.ALLOW_PATH_PREFIXES):
            return None

        # Allow allowlisted namespaces (e.g., login on accounts)
        try:
            match = resolve(path)
            ns = match.namespaces[0] if match.namespaces else ''
            if ns in self.ALLOW_NAMESPACES:
                return None
        except Exception:
            pass

        # Block with a simple 503 page
        return HttpResponse(
            '<!doctype html><html><head><title>Maintenance</title>'
            '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<script src="https://cdn.tailwindcss.com"></script>'
            '</head><body class="min-h-screen bg-gray-50">'
            '<div class="mx-auto max-w-2xl p-6">'
            '<div class="rounded border-l-4 border-yellow-500 bg-yellow-50 p-4 text-yellow-800">'
            '<h1 class="text-lg font-semibold mb-1">We\'ll be back soon</h1>'
            '<div>The platform is currently under maintenance. Please try again later.</div>'
            '</div></div></body></html>',
            status=503,
            content_type='text/html',
        )
