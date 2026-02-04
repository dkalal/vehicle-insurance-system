from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache


class LoginRateLimitMiddleware(MiddlewareMixin):
    """
    Basic login rate limiting for the web UI.

    - Blocks excessive failed attempts per (IP, username) for a cooldown window.
    - On block, redirects back to login with an error message.
    - Counting of failures is done via signals in accounts.signals.
    
    This is a minimal, dependency-free MVP aligned with our security rules.
    """

    def _client_ip(self, request):
        # MVP: Trust REMOTE_ADDR in local/dev. For production, honor X-Forwarded-For as configured.
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')

    def process_request(self, request):
        # Only guard the login POSTs
        if request.method != 'POST':
            return None
        path = (request.path or '')
        if not path.startswith('/accounts/login'):
            return None

        username = request.POST.get('username', '').strip().lower()
        client_ip = self._client_ip(request)
        # Block key set by signals when threshold is exceeded
        block_key = f"login_block:{client_ip}:{username}" if username else f"login_block:{client_ip}"
        try:
            blocked = cache.get(block_key)
        except Exception:
            blocked = False  # fail open if cache backend unavailable

        if blocked:
            messages.error(
                request,
                "Too many failed login attempts. Please try again later."
            )
            return redirect('accounts:login')
        return None


class ForcePasswordChangeMiddleware(MiddlewareMixin):
    def process_request(self, request):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None
        if getattr(user, 'is_super_admin', False):
            return None
        if not getattr(user, 'must_change_password', False):
            return None

        path = request.path or ''

        from django.urls import reverse

        allowed_paths = set()
        try:
            allowed_paths.update({
                reverse('accounts:force_password_change'),
                reverse('accounts:logout'),
                reverse('accounts:login'),
            })
        except Exception:
            allowed_paths.update({'/accounts/login/'})

        if path.startswith('/static/') or path.startswith('/media/'):
            return None
        if path in allowed_paths:
            return None

        messages.warning(request, 'You must set a new password before continuing.')
        return redirect('accounts:force_password_change')
