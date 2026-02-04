"""
Customer model for the Vehicle Insurance system.

Represents both individual and company customers who own vehicles and policies.
"""

from django.db import models
from django.core.validators import RegexValidator
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from .base import BaseModel
from apps.tenants.managers import CustomerManager, TenantAwareSoftDeleteManager


class Customer(BaseModel):
    """
    Customer can be either an Individual or a Company.
    
    **Business Rules:**
    - Must be one of: Individual or Company
    - Individual: requires first_name, last_name, id_number
    - Company: requires company_name, registration_number
    - Email and phone are mandatory for contact
    - Full history tracked for compliance
    """
    
    CUSTOMER_TYPE_INDIVIDUAL = 'individual'
    CUSTOMER_TYPE_COMPANY = 'company'
    
    CUSTOMER_TYPE_CHOICES = [
        (CUSTOMER_TYPE_INDIVIDUAL, 'Individual'),
        (CUSTOMER_TYPE_COMPANY, 'Company'),
    ]
    
    # Customer Type
    customer_type = models.CharField(
        max_length=20,
        choices=CUSTOMER_TYPE_CHOICES,
        db_index=True,
        help_text="Type of customer: individual or company"
    )
    
    # Individual Fields
    first_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="First name (for individuals)"
    )
    
    last_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Last name (for individuals)"
    )
    
    id_number = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="National ID or Passport number (for individuals)"
    )
    
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text="Date of birth (for individuals)"
    )
    
    # Company Fields
    company_name = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Company name (for companies)"
    )
    
    registration_number = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Business registration number (for companies)"
    )
    
    tax_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Tax identification number (for companies)"
    )
    
    # Contact Information (required for both types)
    email = models.EmailField(
        help_text="Primary email address"
    )
    
    phone = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be in format: '+999999999'. Up to 15 digits allowed."
            ),
        ],
        help_text="Primary phone number"
    )
    
    # Address
    address = models.TextField(
        blank=True,
        help_text="Full address"
    )
    
    city = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the customer"
    )
    
    # Managers
    # Default manager is tenant-scoped via CustomerManager, while
    # ``all_objects`` exposes the unscoped soft-delete manager for
    # internal/service-layer use where explicit tenant filters are applied.
    objects = CustomerManager()
    all_objects = TenantAwareSoftDeleteManager()
    
    # History Tracking
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        ordering = ['-created_at']
        base_manager_name = 'all_objects'
        indexes = [
            models.Index(fields=['tenant', 'customer_type']),
            models.Index(fields=['tenant', 'email']),
            models.Index(fields=['tenant', 'id_number']),
            models.Index(fields=['tenant', 'registration_number']),
        ]
        constraints = [
            # Ensure individuals have required fields
            models.CheckConstraint(
                check=(
                    ~models.Q(customer_type='individual') |
                    (models.Q(first_name__isnull=False) & ~models.Q(first_name=''))
                ),
                name='individual_has_first_name'
            ),
            # Ensure companies have company name
            models.CheckConstraint(
                check=(
                    ~models.Q(customer_type='company') |
                    (models.Q(company_name__isnull=False) & ~models.Q(company_name=''))
                ),
                name='company_has_name'
            ),
            models.UniqueConstraint(
                fields=['tenant', 'id_number'],
                condition=(
                    models.Q(deleted_at__isnull=True) &
                    models.Q(customer_type='individual') &
                    ~models.Q(id_number='')
                ),
                name='unique_individual_id_number_per_tenant'
            ),
            models.UniqueConstraint(
                fields=['tenant', 'registration_number'],
                condition=(
                    models.Q(deleted_at__isnull=True) &
                    models.Q(customer_type='company') &
                    ~models.Q(registration_number='')
                ),
                name='unique_company_registration_per_tenant'
            ),
        ]
    
    def __str__(self):
        if self.customer_type == self.CUSTOMER_TYPE_INDIVIDUAL:
            return f"{self.first_name} {self.last_name}"
        return self.company_name
    
    def get_display_name(self):
        """Get formatted display name based on customer type."""
        return str(self)
    
    @property
    def full_name(self):
        """Alias for get_display_name."""
        return self.get_display_name()


# Register for audit logging
auditlog.register(Customer)
