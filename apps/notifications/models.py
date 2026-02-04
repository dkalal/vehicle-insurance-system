from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.models.base import BaseModel
from apps.tenants.models import Tenant

User = get_user_model()


class Notification(BaseModel):
    TYPE_POLICY_EXPIRY = 'policy_expiry'
    TYPE_PAYMENT_DUE = 'payment_due'
    TYPE_COMPLIANCE_ALERT = 'compliance_alert'
    TYPE_SYSTEM_ANNOUNCEMENT = 'system_announcement'
    TYPE_USER_ACTIVITY = 'user_activity'
    TYPE_PAYMENT_VERIFICATION_REQUEST = 'payment_verification_request'
    
    TYPE_CHOICES = [
        (TYPE_POLICY_EXPIRY, 'Policy Expiry'),
        (TYPE_PAYMENT_DUE, 'Payment Due'),
        (TYPE_COMPLIANCE_ALERT, 'Compliance Alert'),
        (TYPE_SYSTEM_ANNOUNCEMENT, 'System Announcement'),
        (TYPE_USER_ACTIVITY, 'User Activity'),
        (TYPE_PAYMENT_VERIFICATION_REQUEST, 'Payment Verification Request'),
    ]
    
    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_CRITICAL = 'critical'
    
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_CRITICAL, 'Critical'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='notifications')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Optional reference to related objects
    policy_id = models.UUIDField(null=True, blank=True)
    vehicle_id = models.UUIDField(null=True, blank=True)
    customer_id = models.UUIDField(null=True, blank=True)
    
    # Notification state
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Optional action URL
    action_url = models.CharField(max_length=500, blank=True)
    action_text = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'notifications_notification'
        indexes = [
            models.Index(fields=['tenant', 'user', '-created_at']),
            models.Index(fields=['tenant', 'user', 'is_read']),
            models.Index(fields=['tenant', 'type', 'priority']),
            models.Index(fields=['tenant', 'vehicle_id', '-created_at']),
            models.Index(fields=['tenant', 'policy_id', 'type']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class TenantNotificationSettings(BaseModel):
    """Per-tenant defaults for notification categories and channels."""

    policy_expiry_enabled = models.BooleanField(default=True)
    payment_notifications_enabled = models.BooleanField(default=True)
    compliance_alerts_enabled = models.BooleanField(default=True)
    system_notifications_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'notifications_tenant_settings'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_active_notification_settings_per_tenant',
            ),
        ]


class UserNotificationPreference(BaseModel):
    """Per-user overrides for notification categories within a tenant."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
    )

    policy_expiry_enabled = models.BooleanField(null=True, blank=True)
    payment_notifications_enabled = models.BooleanField(null=True, blank=True)
    compliance_alerts_enabled = models.BooleanField(null=True, blank=True)
    system_notifications_enabled = models.BooleanField(null=True, blank=True)

    class Meta:
        db_table = 'notifications_user_preferences'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'user'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_active_notification_preferences_per_user',
            ),
        ]
