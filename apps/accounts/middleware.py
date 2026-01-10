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
