from .models import PlatformConfig


def platform_config(request):
    cfg = PlatformConfig.get_solo()
    return {
        'platform_config': cfg,
    }
