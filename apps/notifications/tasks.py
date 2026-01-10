from datetime import timedelta
from django.utils import timezone
from celery import shared_task
from django.conf import settings

from apps.core.models import Policy


@shared_task(bind=True, ignore_result=True)
def send_expiry_reminders(self):
    """
    Background job: find policies expiring within tenant-configured window and emit reminders.
    MVP: logs only; integrate email/SMS later. Tenant isolation is enforced by model managers when used via views,
    but here we must query across tenants so we use Policy._base_manager explicitly with careful filters.
    """
    today = timezone.now().date()
    soon = today + timedelta(days=30)
    qs = Policy._base_manager.filter(
        deleted_at__isnull=True,
        status=Policy.STATUS_ACTIVE,
        end_date__gt=today,
        end_date__lte=soon,
    ).select_related('tenant', 'vehicle', 'vehicle__owner')
    for p in qs.iterator():
        # Placeholder: emit to logging; replace with email/SMS integration
        # Example: notify tenant admins
        print(f"[Reminder] Tenant={p.tenant_id} Policy={p.policy_number} for {p.vehicle.registration_number} expires on {p.end_date}")


@shared_task(bind=True, ignore_result=True)
def refresh_dashboard_metrics(self):
    """
    Optional cache warmer for dashboard metrics per tenant (counts, expiring soon).
    MVP: no cache store; this is a placeholder hook for future optimization.
    """
    return "ok"
