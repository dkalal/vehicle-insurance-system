from datetime import timedelta, date
from django.utils import timezone
from celery import shared_task
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model

from apps.core.models import Policy
from apps.core.models.vehicle_record import VehiclePermit, LATRARecord
from apps.tenants.models import Tenant
from apps.core.services import lifecycle_service
from .services import NotificationGenerator, NotificationService

User = get_user_model()


@shared_task(bind=True, ignore_result=True)
def expire_compliance_records(self):
    """Mark expired policies and permits as expired."""
    today = date.today()
    expired_count = 0
    
    # Expire policies
    active_policies = Policy.objects.filter(
        status=Policy.STATUS_ACTIVE,
        end_date__lt=today,
        deleted_at__isnull=True
    )
    for policy in active_policies:
        try:
            lifecycle_service.expire_entity(policy.id, Policy)
            expired_count += 1
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error expiring policy {policy.id}: {e}")
    
    # Expire permits
    active_permits = VehiclePermit.objects.filter(
        status=VehiclePermit.STATUS_ACTIVE,
        end_date__lt=today,
        deleted_at__isnull=True
    )
    for permit in active_permits:
        try:
            lifecycle_service.expire_entity(permit.id, VehiclePermit)
            expired_count += 1
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error expiring permit {permit.id}: {e}")
    
    # Expire LATRA records
    active_latra = LATRARecord.objects.filter(
        status=LATRARecord.STATUS_ACTIVE,
        end_date__lt=today,
        deleted_at__isnull=True
    )
    for latra in active_latra:
        try:
            lifecycle_service.expire_entity(latra.id, LATRARecord)
            expired_count += 1
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error expiring LATRA {latra.id}: {e}")
    
    return f"Expired {expired_count} records"


@shared_task(bind=True, ignore_result=True)
def generate_daily_notifications(self):
    """Generate daily notifications for all tenants."""
    tenants = Tenant.objects.filter(is_active=True)
    
    for tenant in tenants:
        try:
            # Generate policy expiry notifications
            NotificationGenerator.generate_policy_expiry_notifications(tenant)
            
            # Generate payment due notifications
            NotificationGenerator.generate_payment_due_notifications(tenant)
            
        except Exception as e:
            # Log error but continue with other tenants
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating notifications for tenant {tenant.id}: {e}")


@shared_task(bind=True, ignore_result=True)
def cleanup_old_notifications(self):
    """Clean up old notifications for all tenants."""
    tenants = Tenant.objects.filter(is_active=True)
    
    for tenant in tenants:
        try:
            NotificationService.cleanup_old_notifications(tenant=tenant, days=90)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error cleaning notifications for tenant {tenant.id}: {e}")


@shared_task(bind=True, ignore_result=True)
def send_expiry_reminders(self):
    """
    Legacy task - now handled by generate_daily_notifications
    """
    return "deprecated - use generate_daily_notifications"


@shared_task(bind=True, ignore_result=True)
def refresh_dashboard_metrics(self):
    """
    Optional cache warmer for dashboard metrics per tenant (counts, expiring soon).
    MVP: no cache store; this is a placeholder hook for future optimization.
    """
    return "ok"
