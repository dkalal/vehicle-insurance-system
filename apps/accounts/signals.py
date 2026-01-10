from django.conf import settings
from django.contrib.auth.signals import user_login_failed, user_logged_in
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone

ATTEMPTS = getattr(settings, 'LOGIN_RATE_LIMIT_ATTEMPTS', 5)
WINDOW = getattr(settings, 'LOGIN_RATE_LIMIT_WINDOW_SECONDS', 300)
BLOCK = getattr(settings, 'LOGIN_RATE_LIMIT_BLOCK_SECONDS', 900)


def _client_ip(request):
    if not request:
        return '0.0.0.0'
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    username = (credentials or {}).get('username', '')
    username = (username or '').strip().lower()
    ip = _client_ip(request)

    fail_key = f"login_fail:{ip}:{username}" if username else f"login_fail:{ip}"
    block_key = f"login_block:{ip}:{username}" if username else f"login_block:{ip}"

    # increment failure count within rolling window
    try:
        # get current count
        count = cache.get(fail_key, 0) + 1
        # set/update with window expiry
        cache.set(fail_key, count, timeout=WINDOW)
    except Exception:
        # fail safe: do nothing if cache backend unavailable
        return

    # apply block when threshold exceeded
    if count >= ATTEMPTS:
        cache.set(block_key, 1, timeout=BLOCK)


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    # rotate session key as belt-and-suspenders
    try:
        if hasattr(request, 'session'):
            request.session.cycle_key()
    except Exception:
        pass

    # update last_login_at for our custom field (separate from Django's last_login)
    try:
        user.last_login_at = timezone.now()
        user.save(update_fields=['last_login_at'])
    except Exception:
        pass

    # clear any failure and block keys for this ip/username
    try:
        ip = _client_ip(request)
        username = (getattr(user, 'username', '') or '').strip().lower()
        keys = [
            f"login_fail:{ip}:{username}",
            f"login_block:{ip}:{username}",
            f"login_fail:{ip}",
            f"login_block:{ip}",
        ]
        for k in keys:
            cache.delete(k)
    except Exception:
        pass
