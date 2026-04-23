from django.db import models
from django.conf import settings
from .base import BaseModel


class SupportRequest(BaseModel):
    REQUEST_TYPE_VEHICLE_COMPLIANCE = 'vehicle_compliance'
    REQUEST_TYPE_POLICY = 'policy'
    REQUEST_TYPE_PERMIT = 'permit'
    REQUEST_TYPE_PAYMENT = 'payment'
    REQUEST_TYPE_ACCESS = 'access'
    REQUEST_TYPE_DATA_CORRECTION = 'data_correction'
    REQUEST_TYPE_GENERAL = 'general'

    REQUEST_TYPE_CHOICES = [
        (REQUEST_TYPE_VEHICLE_COMPLIANCE, 'Vehicle compliance issue'),
        (REQUEST_TYPE_POLICY, 'Insurance/policy issue'),
        (REQUEST_TYPE_PERMIT, 'Permit/LATRA issue'),
        (REQUEST_TYPE_PAYMENT, 'Payment issue'),
        (REQUEST_TYPE_ACCESS, 'Staff access/account issue'),
        (REQUEST_TYPE_DATA_CORRECTION, 'Data correction request'),
        (REQUEST_TYPE_GENERAL, 'General support'),
    ]

    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_WAITING_ON_TENANT = 'waiting_on_tenant'
    STATUS_RESOLVED = 'resolved'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_WAITING_ON_TENANT, 'Waiting On Tenant'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_HIGH, 'High'),
    ]

    subject = models.CharField(max_length=255, db_index=True)
    message = models.TextField()
    request_type = models.CharField(
        max_length=40,
        choices=REQUEST_TYPE_CHOICES,
        default=REQUEST_TYPE_GENERAL,
        db_index=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_NORMAL,
        db_index=True,
    )
    vehicle_registration_number = models.CharField(max_length=50, blank=True)
    policy_reference = models.CharField(max_length=100, blank=True)
    permit_reference = models.CharField(max_length=100, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='support_assigned_set',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_summary = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'request_type']),
            models.Index(fields=['tenant', 'priority']),
            models.Index(fields=['tenant', 'created_at']),
        ]

    def __str__(self):
        return f"{self.tenant_id}:{self.subject} ({self.status})"

    @property
    def primary_reference(self):
        return self.vehicle_registration_number or self.policy_reference or self.permit_reference or ''


class SupportRequestEvent(BaseModel):
    EVENT_CREATED = 'created'
    EVENT_STATUS_CHANGED = 'status_changed'
    EVENT_ASSIGNMENT_CHANGED = 'assignment_changed'
    EVENT_PUBLIC_REPLY = 'public_reply'
    EVENT_INTERNAL_NOTE = 'internal_note'
    EVENT_RESOLVED = 'resolved'
    EVENT_REOPENED = 'reopened'

    EVENT_TYPE_CHOICES = [
        (EVENT_CREATED, 'Created'),
        (EVENT_STATUS_CHANGED, 'Status changed'),
        (EVENT_ASSIGNMENT_CHANGED, 'Assignment changed'),
        (EVENT_PUBLIC_REPLY, 'Public reply'),
        (EVENT_INTERNAL_NOTE, 'Internal note'),
        (EVENT_RESOLVED, 'Resolved'),
        (EVENT_REOPENED, 'Reopened'),
    ]

    VISIBILITY_TENANT = 'tenant'
    VISIBILITY_INTERNAL = 'internal'

    VISIBILITY_CHOICES = [
        (VISIBILITY_TENANT, 'Tenant visible'),
        (VISIBILITY_INTERNAL, 'Internal only'),
    ]

    support_request = models.ForeignKey(
        'SupportRequest',
        on_delete=models.PROTECT,
        related_name='events',
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES, db_index=True)
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_TENANT,
        db_index=True,
    )
    message = models.TextField(blank=True)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    previous_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='support_previous_assignment_events',
    )
    new_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='support_new_assignment_events',
    )

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [
            models.Index(fields=['tenant', 'support_request', 'created_at']),
            models.Index(fields=['tenant', 'visibility', 'created_at']),
        ]

    def __str__(self):
        return f"{self.support_request_id}:{self.event_type}"
