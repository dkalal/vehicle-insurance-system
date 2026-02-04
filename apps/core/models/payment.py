"""
Payment model for the Vehicle Insurance system.

Represents payments made for insurance policies.
"""

from django.db import models
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from .base import BaseModel


class Payment(BaseModel):
    """
    Payment for an insurance policy.
    
    **Business Rules:**
    - Full payment only (no partial payments)
    - Payment triggers policy activation when full amount is received
    - All payments are immutable (cannot be deleted)
    - Payments are audited for compliance
    """
    
    PAYMENT_METHOD_CASH = 'cash'
    PAYMENT_METHOD_BANK_TRANSFER = 'bank_transfer'
    PAYMENT_METHOD_MOBILE_MONEY = 'mobile_money'
    PAYMENT_METHOD_CHECK = 'check'
    PAYMENT_METHOD_CARD = 'card'
    
    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_CASH, 'Cash'),
        (PAYMENT_METHOD_BANK_TRANSFER, 'Bank Transfer'),
        (PAYMENT_METHOD_MOBILE_MONEY, 'Mobile Money'),
        (PAYMENT_METHOD_CHECK, 'Check'),
        (PAYMENT_METHOD_CARD, 'Credit/Debit Card'),
    ]
    
    # Related Policy
    policy = models.ForeignKey(
        'Policy',
        on_delete=models.PROTECT,
        related_name='payments',
        help_text="Policy this payment is for"
    )
    
    # Payment Details
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Payment amount"
    )
    
    payment_date = models.DateTimeField(
        help_text="When payment was made"
    )
    
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        help_text="Method of payment"
    )
    
    reference_number = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Payment reference/transaction number"
    )
    
    # Additional Information
    payer_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of person who made payment (if different from policy holder)"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the payment"
    )
    
    # Verification
    is_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether payment has been verified"
    )
    
    verified_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_payments',
        help_text="User who verified the payment"
    )
    
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was verified"
    )
    
    # History Tracking
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['tenant', 'policy']),
            models.Index(fields=['tenant', 'payment_date']),
            models.Index(fields=['tenant', 'is_verified']),
            models.Index(fields=['reference_number']),
        ]
        constraints = [
            # Payment amount must be positive
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name='payment_amount_positive'
            ),
        ]
    
    def __str__(self):
        return f"Payment {self.reference_number} - {self.amount} for {self.policy.policy_number}"

    @property
    def review_status(self):
        """Derived review status based on verification flag and notes.

        - "approved" when is_verified is True
        - "rejected" when notes start with a rejection marker
        - "pending" otherwise
        """
        if self.is_verified:
            return 'approved'
        notes = (self.notes or '').strip().upper()
        if notes.startswith('[REJECTED'):
            return 'rejected'
        return 'pending'
    
    def verify(self, verified_by):
        """
        Verify this payment.
        
        Args:
            verified_by: User instance who is verifying.
        """
        from django.utils import timezone
        self.is_verified = True
        self.verified_by = verified_by
        self.verified_at = timezone.now()
        self.save(update_fields=['is_verified', 'verified_by', 'verified_at', 'updated_at'])


# Register for audit logging
auditlog.register(Payment)
