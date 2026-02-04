from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models
from datetime import timedelta
from .models import Notification, TenantNotificationSettings, UserNotificationPreference

User = get_user_model()


class NotificationDeliveryService:
    """Dispatch notifications to delivery channels.

    For now this is in-app only, but the abstraction allows plugging in
    email/SMS/WhatsApp/push via Celery without touching domain services.
    """

    @staticmethod
    def dispatch(notification, channels=None):
        # In-app is implicit via the Notification row itself.
        # Additional channels (email/SMS/etc.) can be wired here later.
        return notification


class NotificationService:
    
    @staticmethod
    def _get_category_for_type(notification_type):
        """Map notification type to a high-level category for preferences."""
        if notification_type == Notification.TYPE_POLICY_EXPIRY:
            return 'policy_expiry'
        if notification_type in (Notification.TYPE_PAYMENT_DUE, Notification.TYPE_PAYMENT_VERIFICATION_REQUEST):
            return 'payments'
        if notification_type == Notification.TYPE_COMPLIANCE_ALERT:
            return 'compliance'
        return 'system'

    @staticmethod
    def _is_category_enabled(*, tenant, user, notification_type):
        """Check tenant + user preferences for a given notification type."""
        category = NotificationService._get_category_for_type(notification_type)

        # Tenant defaults
        tenant_settings = TenantNotificationSettings.objects.filter(
            tenant=tenant
        ).first()

        def _tenant_enabled():
            if not tenant_settings:
                return True
            if category == 'policy_expiry':
                return bool(tenant_settings.policy_expiry_enabled)
            if category == 'payments':
                return bool(tenant_settings.payment_notifications_enabled)
            if category == 'compliance':
                return bool(tenant_settings.compliance_alerts_enabled)
            if category == 'system':
                return bool(tenant_settings.system_notifications_enabled)
            return True

        # User overrides
        user_pref = UserNotificationPreference.objects.filter(
            tenant=tenant,
            user=user
        ).first()

        if not user_pref:
            return _tenant_enabled()

        if category == 'policy_expiry' and user_pref.policy_expiry_enabled is not None:
            return bool(user_pref.policy_expiry_enabled)
        if category == 'payments' and user_pref.payment_notifications_enabled is not None:
            return bool(user_pref.payment_notifications_enabled)
        if category == 'compliance' and user_pref.compliance_alerts_enabled is not None:
            return bool(user_pref.compliance_alerts_enabled)
        if category == 'system' and user_pref.system_notifications_enabled is not None:
            return bool(user_pref.system_notifications_enabled)

        return _tenant_enabled()

    @staticmethod
    def create_notification(*, tenant, user, type, title, message, priority=Notification.PRIORITY_MEDIUM,
                          policy_id=None, vehicle_id=None, customer_id=None, action_url='', action_text=''):
        """Create a new notification for a user, respecting preferences."""
        if not NotificationService._is_category_enabled(
            tenant=tenant,
            user=user,
            notification_type=type,
        ):
            return None

        notification = Notification.objects.create(
            tenant=tenant,
            user=user,
            type=type,
            priority=priority,
            title=title,
            message=message,
            policy_id=policy_id,
            vehicle_id=vehicle_id,
            customer_id=customer_id,
            action_url=action_url,
            action_text=action_text,
        )

        return NotificationDeliveryService.dispatch(notification)
    
    @staticmethod
    def create_policy_expiry_notification(*, tenant, user, policy, days_until_expiry):
        """Create policy expiry notification."""
        if days_until_expiry <= 7:
            priority = Notification.PRIORITY_HIGH
        elif days_until_expiry <= 15:
            priority = Notification.PRIORITY_MEDIUM
        else:
            priority = Notification.PRIORITY_LOW
            
        title = f"Policy Expiring in {days_until_expiry} Days"
        message = f"Policy {policy.policy_number} for vehicle {policy.vehicle.registration_number} expires on {policy.end_date.strftime('%B %d, %Y')}."
        
        return NotificationService.create_notification(
            tenant=tenant,
            user=user,
            type=Notification.TYPE_POLICY_EXPIRY,
            priority=priority,
            title=title,
            message=message,
            policy_id=policy.id,
            vehicle_id=policy.vehicle.id,
            action_url=f'/dashboard/policies/{policy.id}/',
            action_text='View Policy'
        )
    
    @staticmethod
    def create_payment_due_notification(*, tenant, user, policy):
        """Create payment due notification."""
        title = "Payment Required"
        message = f"Payment is required to activate policy {policy.policy_number} for vehicle {policy.vehicle.registration_number}."
        
        return NotificationService.create_notification(
            tenant=tenant,
            user=user,
            type=Notification.TYPE_PAYMENT_DUE,
            priority=Notification.PRIORITY_HIGH,
            title=title,
            message=message,
            policy_id=policy.id,
            vehicle_id=policy.vehicle.id,
            action_url=f'/dashboard/payments/create/?policy={policy.id}',
            action_text='Make Payment'
        )
    
    @staticmethod
    def create_payment_verification_request(*, tenant, policy, created_by):
        """Notify tenant admins/managers that a payment was recorded and needs verification.

        This is triggered when an agent/staff user records a payment that remains
        unverified. Notifications are sent only within the same tenant and only
        to active Admin and Manager users.
        """
        # Find all active admins/managers in this tenant
        recipients = User.objects.filter(
            tenant=tenant,
            is_active=True,
            role__in=[User.ROLE_ADMIN, User.ROLE_MANAGER],
        )

        if not recipients.exists():
            return None

        # Compose a concise, action-focused message
        actor_name = created_by.get_full_name() or created_by.username
        title = "Payment recorded and pending verification"
        message = (
            f"{actor_name} recorded a payment for policy {policy.policy_number} "
            f"for vehicle {policy.vehicle.registration_number}. "
            "Please review and verify the payment to activate coverage if fully paid."
        )

        created = []
        for user in recipients:
            created.append(
                NotificationService.create_notification(
                    tenant=tenant,
                    user=user,
                    type=Notification.TYPE_PAYMENT_VERIFICATION_REQUEST,
                    priority=Notification.PRIORITY_HIGH,
                    title=title,
                    message=message,
                    policy_id=policy.id,
                    vehicle_id=policy.vehicle.id,
                    action_url=f'/dashboard/policies/{policy.id}/',
                    action_text='Review Payment',
                )
            )
        return created
    
    @staticmethod
    def create_cancellation_notification(*, tenant, entity, cancelled_by, reason, note=''):
        """Notify relevant users about policy/permit cancellation."""
        from apps.core.models import Policy
        from apps.core.models.vehicle_record import VehiclePermit, LATRARecord
        
        if isinstance(entity, Policy):
            entity_type = 'Policy'
            entity_ref = entity.policy_number
            vehicle = entity.vehicle
        elif isinstance(entity, (VehiclePermit, LATRARecord)):
            entity_type = 'Permit'
            entity_ref = getattr(entity, 'reference_number', getattr(entity, 'latra_number', 'N/A'))
            vehicle = entity.vehicle
        else:
            return None
        
        actor_name = cancelled_by.get_full_name() or cancelled_by.username
        reason_display = dict(entity.CANCELLATION_REASON_CHOICES).get(reason, reason)
        
        title = f"{entity_type} Cancelled"
        message = (
            f"{entity_type} {entity_ref} for vehicle {vehicle.registration_number} "
            f"was cancelled by {actor_name}. Reason: {reason_display}."
        )
        if note:
            message += f" Note: {note}"
        
        # Notify admins and managers
        recipients = User.objects.filter(
            tenant=tenant,
            is_active=True,
            role__in=[User.ROLE_ADMIN, User.ROLE_MANAGER],
        )
        
        created = []
        for user in recipients:
            created.append(
                NotificationService.create_notification(
                    tenant=tenant,
                    user=user,
                    type=Notification.TYPE_COMPLIANCE_ALERT,
                    priority=Notification.PRIORITY_HIGH,
                    title=title,
                    message=message,
                    vehicle_id=vehicle.id,
                    action_url=f'/dashboard/vehicles/{vehicle.id}/',
                    action_text='View Vehicle',
                )
            )
        return created
    
    @staticmethod
    def handle_event(*, event_type, tenant, actor=None, context=None):
        """Handle a high-level notification event.

        This is a thin abstraction to make it easier to add new event types
        without pushing business logic into views.
        """
        context = context or {}

        if event_type == 'payment_pending_verification':
            policy = context.get('policy')
            created_by = actor or context.get('created_by')
            if not policy or not created_by:
                return []
            return NotificationService.create_payment_verification_request(
                tenant=tenant,
                policy=policy,
                created_by=created_by,
            )

        if event_type == 'compliance_record_cancelled':
            entity = context.get('entity')
            reason = context.get('reason')
            note = context.get('note', '')
            if not entity or not reason:
                return []
            cancelled_by = actor or context.get('cancelled_by')
            if not cancelled_by:
                return []
            return NotificationService.create_cancellation_notification(
                tenant=tenant,
                entity=entity,
                cancelled_by=cancelled_by,
                reason=reason,
                note=note,
            )

        # Unknown or unhandled event type
        return []
    
    @staticmethod
    def get_user_notifications(*, tenant, user, limit=20, unread_only=False, types=None, priority=None,
                               created_from=None, created_to=None):
        """Get notifications for a user with optional filtering."""
        qs = Notification.objects.filter(tenant=tenant, user=user)

        if unread_only:
            qs = qs.filter(is_read=False)

        if types:
            if isinstance(types, str):
                types = [types]
            qs = qs.filter(type__in=types)

        if priority:
            qs = qs.filter(priority=priority)

        if created_from:
            qs = qs.filter(created_at__gte=created_from)

        if created_to:
            qs = qs.filter(created_at__lte=created_to)

        return qs.order_by('-created_at')[:limit]
    
    @staticmethod
    def get_unread_count(*, tenant, user):
        """Get count of unread notifications for a user."""
        return Notification.objects.filter(
            tenant=tenant, 
            user=user, 
            is_read=False
        ).count()
    
    @staticmethod
    def mark_all_as_read(*, tenant, user):
        """Mark all notifications as read for a user."""
        now = timezone.now()
        return Notification.objects.filter(
            tenant=tenant,
            user=user,
            is_read=False
        ).update(is_read=True, read_at=now)
    
    @staticmethod
    def cleanup_old_notifications(*, tenant, days=90):
        """Clean up old notifications (older than specified days)."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return Notification.objects.filter(
            tenant=tenant,
            created_at__lt=cutoff_date,
            deleted_at__isnull=True,
        ).update(deleted_at=timezone.now())


# Notification generators for background tasks
class NotificationGenerator:
    
    @staticmethod
    def generate_policy_expiry_notifications(tenant):
        """Generate policy expiry notifications for a tenant."""
        from apps.core.models import Policy
        
        today = timezone.now().date()
        
        # Check for policies expiring in 30, 15, and 7 days
        for days in [30, 15, 7]:
            expiry_date = today + timedelta(days=days)
            
            policies = Policy.objects.filter(
                tenant=tenant,
                status=Policy.STATUS_ACTIVE,
                end_date=expiry_date
            ).select_related('vehicle', 'vehicle__owner')
            
            for policy in policies:
                # Check if notification already exists for this policy and timeframe
                existing = Notification.objects.filter(
                    tenant=tenant,
                    type=Notification.TYPE_POLICY_EXPIRY,
                    policy_id=policy.id,
                    created_at__date=today
                ).exists()
                
                if not existing:
                    # Get relevant users (policy creator, vehicle owner, admins)
                    users = User.objects.filter(
                        tenant=tenant,
                        is_active=True
                    ).filter(
                        models.Q(id=policy.created_by_id) |
                        models.Q(role__in=['admin', 'manager'])
                    ).distinct()
                    
                    for user in users:
                        NotificationService.create_policy_expiry_notification(
                            tenant=tenant,
                            user=user,
                            policy=policy,
                            days_until_expiry=days
                        )
    
    @staticmethod
    def generate_payment_due_notifications(tenant):
        """Generate payment due notifications for pending policies."""
        from apps.core.models import Policy
        
        policies = Policy.objects.filter(
            tenant=tenant,
            status=Policy.STATUS_PENDING_PAYMENT
        ).select_related('vehicle')
        
        today = timezone.now().date()
        
        for policy in policies:
            # Check if notification sent in last 3 days
            recent_notification = Notification.objects.filter(
                tenant=tenant,
                type=Notification.TYPE_PAYMENT_DUE,
                policy_id=policy.id,
                created_at__date__gte=today - timedelta(days=3)
            ).exists()
            
            if not recent_notification:
                users = User.objects.filter(
                    tenant=tenant,
                    is_active=True,
                    role__in=['admin', 'manager', 'agent']
                )
                
                for user in users:
                    NotificationService.create_payment_due_notification(
                        tenant=tenant,
                        user=user,
                        policy=policy
                    )