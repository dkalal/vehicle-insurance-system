"""
Policy model for the Vehicle Insurance system.

Represents insurance policies covering vehicles.
"""

from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from .base import BaseModel


class Policy(BaseModel):
    """
    Insurance policy covering a vehicle.
    
    **CRITICAL Business Rules:**
    - Policy becomes ACTIVE only after full payment
    - Start and end dates are flexible (set by tenant admin)
    - Renewal extends existing policy
    - Vehicle can have ONLY ONE active policy at a time
    - Policy history is immutable (never delete active/expired policies)
    """
    
    STATUS_DRAFT = 'draft'
    STATUS_PENDING_PAYMENT = 'pending_payment'
    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'
    
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PENDING_PAYMENT, 'Pending Payment'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    
    # Policy Identification
    policy_number = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Unique policy number"
    )
    
    # Coverage
    vehicle = models.ForeignKey(
        'Vehicle',
        on_delete=models.PROTECT,
        related_name='policies',
        help_text="Vehicle covered by this policy"
    )
    
    # Policy Period
    start_date = models.DateField(
        help_text="Policy start date"
    )
    
    end_date = models.DateField(
        help_text="Policy end date"
    )
    
    # Financial
    premium_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Premium amount for this policy"
    )
    
    coverage_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum coverage/insured value"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
        help_text="Current status of the policy"
    )
    
    # Additional Information
    policy_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of policy (e.g., Comprehensive, Third Party)"
    )
    
    terms_and_conditions = models.TextField(
        blank=True,
        help_text="Policy terms and conditions"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes"
    )
    
    # Lifecycle tracking
    activated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When policy was activated (after payment)"
    )
    
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When policy was cancelled"
    )
    
    cancelled_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='cancelled_policies',
        help_text="User who cancelled the policy"
    )
    
    CANCELLATION_REASON_CUSTOMER_REQUEST = 'customer_request'
    CANCELLATION_REASON_NON_PAYMENT = 'non_payment'
    CANCELLATION_REASON_VEHICLE_SOLD = 'vehicle_sold'
    CANCELLATION_REASON_DUPLICATE = 'duplicate'
    CANCELLATION_REASON_ERROR = 'data_error'
    CANCELLATION_REASON_OTHER = 'other'
    
    CANCELLATION_REASON_CHOICES = [
        (CANCELLATION_REASON_CUSTOMER_REQUEST, 'Customer Request'),
        (CANCELLATION_REASON_NON_PAYMENT, 'Non-Payment'),
        (CANCELLATION_REASON_VEHICLE_SOLD, 'Vehicle Sold'),
        (CANCELLATION_REASON_DUPLICATE, 'Duplicate Entry'),
        (CANCELLATION_REASON_ERROR, 'Data Error'),
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
    
    # History Tracking
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = 'Policy'
        verbose_name_plural = 'Policies'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'vehicle']),
            models.Index(fields=['tenant', 'start_date']),
            models.Index(fields=['tenant', 'end_date']),
            models.Index(fields=['policy_number']),
        ]
        constraints = [
            # End date must be after start date
            models.CheckConstraint(
                check=models.Q(end_date__gt=models.F('start_date')),
                name='end_date_after_start_date'
            ),
            # Premium must be positive
            models.CheckConstraint(
                check=models.Q(premium_amount__gt=0),
                name='premium_must_be_positive'
            ),
            models.UniqueConstraint(
                fields=['tenant', 'policy_number'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_policy_number_per_tenant'
            ),
        ]
    
    def __str__(self):
        return f"Policy {self.policy_number} - {self.vehicle}"
    
    def clean(self):
        """
        Validate policy before saving.
        """
        super().clean()
        
        # Check if vehicle already has an active policy overlapping this period
        # Business rule: a vehicle cannot have more than one ACTIVE policy
        # for the same coverage window. Non-overlapping future/ historical
        # policies are allowed.
        if self.status == self.STATUS_ACTIVE and self.vehicle_id:
            from django.db.models import Q
            active_policies = Policy._base_manager.filter(
                tenant=self.tenant,
                deleted_at__isnull=True,
                vehicle=self.vehicle,
                status=self.STATUS_ACTIVE,
                start_date__lte=self.end_date,
                end_date__gte=self.start_date,
            ).exclude(pk=self.pk)

            if active_policies.exists():
                raise ValidationError({
                    'vehicle': 'This vehicle already has an active policy in this coverage period. '
                               'Only one active policy per vehicle is allowed.'
                })
    
    def get_total_paid(self):
        """
        Calculate total amount paid for this policy.
        
        Returns:
            Decimal: Total paid amount.
        """
        from .payment import Payment
        payments = Payment._base_manager.filter(
            tenant=self.tenant,
            deleted_at__isnull=True,
            policy=self,
            is_verified=True,
        ).only('amount')
        return sum((p.amount for p in payments), Decimal('0.00'))
    
    def is_fully_paid(self):
        """
        Check if policy is fully paid.
        
        Returns:
            Boolean: True if fully paid.
        """
        return self.get_total_paid() >= self.premium_amount
    
    def can_activate(self):
        """
        Check if policy can be activated.
        
        Requirements:
        1. Status is pending_payment or draft
        2. Fully paid
        3. Vehicle doesn't have another active policy
        
        Returns:
            Tuple: (can_activate, reason)
        """
        if self.status == self.STATUS_ACTIVE:
            return False, "Policy is already active"
        
        if not self.is_fully_paid():
            return False, "Policy must be fully paid before activation"
        
        # Check vehicle doesn't have active policy
        active_policies = Policy._base_manager.filter(
            tenant=self.tenant,
            deleted_at__isnull=True,
            vehicle=self.vehicle,
            status=self.STATUS_ACTIVE,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date,
        ).exclude(pk=self.pk)
        
        if active_policies.exists():
            return False, "Vehicle already has an active policy"
        
        return True, "Can be activated"
    
    def is_immutable(self):
        """Check if policy is immutable (cannot be edited)."""
        return self.status == self.STATUS_ACTIVE
    
    def is_active(self):
        """Check if policy is currently active."""
        return self.status == self.STATUS_ACTIVE
    
    def is_expired(self):
        """Check if policy is expired."""
        from django.utils import timezone
        from datetime import date
        return (self.status == self.STATUS_ACTIVE and 
                self.end_date < date.today())
    
    @classmethod
    def generate_policy_number(cls, tenant):
        """
        Generate a unique policy number for a tenant.
        
        Format: POL-{YEAR}-{TENANT_SLUG}-{SEQUENCE}
        
        Args:
            tenant: Tenant instance.
            
        Returns:
            String: Generated policy number.
        """
        from datetime import datetime
        year = datetime.now().year
        
        # Get last policy number for this tenant and year
        prefix = f"POL-{year}-{tenant.slug.upper()}"
        last_policy = cls._base_manager.filter(
            tenant=tenant,
            deleted_at__isnull=True,
            policy_number__startswith=prefix,
        ).order_by('-policy_number').first()
        
        if last_policy:
            # Extract sequence number and increment
            try:
                sequence = int(last_policy.policy_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                sequence = 1
        else:
            sequence = 1
        
        return f"{prefix}-{sequence:05d}"


# Register for audit logging
auditlog.register(Policy)
