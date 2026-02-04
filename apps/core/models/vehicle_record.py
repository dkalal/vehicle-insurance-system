from django.db import models
from django.core.exceptions import ValidationError
from auditlog.registry import auditlog
from .base import TenantAwareModel, AuditableModel, SoftDeleteModel


class VehicleRecord(TenantAwareModel, AuditableModel, SoftDeleteModel):
    STATUS_DRAFT = 'draft'
    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    vehicle = models.ForeignKey(
        'Vehicle',
        on_delete=models.PROTECT,
        related_name='%(class)s_set',
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    
    # Lifecycle tracking
    activated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When record was activated"
    )
    
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When record was cancelled"
    )
    
    cancelled_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='cancelled_%(class)s_set',
        help_text="User who cancelled the record"
    )
    
    CANCELLATION_REASON_CUSTOMER_REQUEST = 'customer_request'
    CANCELLATION_REASON_VEHICLE_SOLD = 'vehicle_sold'
    CANCELLATION_REASON_DUPLICATE = 'duplicate'
    CANCELLATION_REASON_ERROR = 'data_error'
    CANCELLATION_REASON_EXPIRED_EARLY = 'expired_early'
    CANCELLATION_REASON_OTHER = 'other'
    
    CANCELLATION_REASON_CHOICES = [
        (CANCELLATION_REASON_CUSTOMER_REQUEST, 'Customer Request'),
        (CANCELLATION_REASON_VEHICLE_SOLD, 'Vehicle Sold'),
        (CANCELLATION_REASON_DUPLICATE, 'Duplicate Entry'),
        (CANCELLATION_REASON_ERROR, 'Data Error'),
        (CANCELLATION_REASON_EXPIRED_EARLY, 'Expired Early'),
        (CANCELLATION_REASON_OTHER, 'Other'),
    ]
    
    cancellation_reason = models.CharField(
        max_length=50,
        choices=CANCELLATION_REASON_CHOICES,
        blank=True,
        help_text="Reason for cancellation"
    )
    
    cancellation_note = models.TextField(
        blank=True,
        help_text="Additional cancellation details"
    )

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date must be after start date.'})
        tenant_id = getattr(self, 'tenant_id', None)
        vehicle = getattr(self, 'vehicle', None)
        if vehicle is not None and tenant_id is not None and vehicle.tenant_id != tenant_id:
            raise ValidationError({'vehicle': 'Vehicle must belong to the same tenant as this record.'})

    def save(self, *args, **kwargs):
        if self.vehicle_id and not getattr(self, 'tenant_id', None):
            self.tenant_id = self.vehicle.tenant_id
        elif self.vehicle_id and getattr(self, 'tenant_id', None) and self.vehicle.tenant_id != self.tenant_id:
            raise ValidationError({'tenant': 'Tenant must match vehicle tenant.'})
        super().save(*args, **kwargs)
    
    def is_immutable(self):
        """Check if record is immutable (cannot be edited)."""
        return self.status == self.STATUS_ACTIVE


class LATRARecord(VehicleRecord):
    latra_number = models.CharField(max_length=100)
    license_type = models.CharField(max_length=100)
    route = models.CharField(max_length=255, blank=True)
    issuing_authority = models.CharField(max_length=100, default='LATRA')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'vehicle', 'status']),
            models.Index(fields=['tenant', 'latra_number']),
            models.Index(fields=['tenant', 'start_date']),
            models.Index(fields=['tenant', 'end_date']),
        ]

    def __str__(self):
        return f"{self.latra_number}"


class PermitType(TenantAwareModel):
    name = models.CharField(max_length=100)
    conflicts_with = models.ManyToManyField('self', blank=True)
    # Simple active flag instead of hard deletes for configuration data
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['tenant_id', 'name']
        indexes = [
            models.Index(fields=['tenant', 'name']),
        ]
        unique_together = (
            ('tenant', 'name'),
        )

    def __str__(self):
        return self.name


class VehiclePermit(VehicleRecord):
    permit_type = models.ForeignKey(
        PermitType,
        on_delete=models.PROTECT,
        related_name='vehicle_permits',
    )
    reference_number = models.CharField(max_length=100)
    document = models.FileField(upload_to='vehicle_permits/', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'vehicle', 'status']),
            models.Index(fields=['tenant', 'permit_type']),
            models.Index(fields=['tenant', 'start_date']),
            models.Index(fields=['tenant', 'end_date']),
        ]

    def __str__(self):
        return self.reference_number


auditlog.register(LATRARecord)
auditlog.register(PermitType)
auditlog.register(VehiclePermit)
