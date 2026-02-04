from datetime import timedelta
from typing import Dict, Any

from django.utils import timezone

from auditlog.models import LogEntry

from apps.tenants.models import Tenant
from apps.core.models import SupportRequest

from .models import PlatformConfig


def get_platform_overview() -> Dict[str, Any]:
    """Aggregate high-level, read-only metrics for the Super Admin home.

    This function intentionally stays read-only and cross-tenant, and is only
    consumed from Super Admin views that are already gated by the
    SuperAdminRequiredMixin.
    """
    cfg = PlatformConfig.get_solo()

    tenants_qs = Tenant.objects.all()
    tenants_total = tenants_qs.count()
    tenants_active = tenants_qs.filter(is_active=True, deleted_at__isnull=True).count()
    tenants_inactive = tenants_qs.filter(is_active=False, deleted_at__isnull=True).count()
    tenants_deleted = tenants_qs.filter(deleted_at__isnull=False).count()

    open_support = (
        SupportRequest._base_manager
        .filter(status=SupportRequest.STATUS_OPEN)
        .count()
    )

    last_audit_timestamp = (
        LogEntry.objects
        .order_by('-timestamp')
        .values_list('timestamp', flat=True)
        .first()
    )

    recent_window_start = timezone.now() - timedelta(hours=24)
    recent_audit_entries = (
        LogEntry.objects
        .filter(timestamp__gte=recent_window_start)
        .count()
    )

    return {
        'tenants_total': tenants_total,
        'tenants_active': tenants_active,
        'tenants_inactive': tenants_inactive,
        'tenants_deleted': tenants_deleted,
        'support_open': open_support,
        'maintenance_mode': cfg.maintenance_mode,
        'last_audit_timestamp': last_audit_timestamp,
        'audit_entries_24h': recent_audit_entries,
    }
