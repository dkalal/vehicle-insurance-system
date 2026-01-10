"""
Tenant model for multi-tenancy support.

This is the core model representing insurance companies using the platform.
Each tenant is completely isolated from others at the data level.
"""

from django.db import models
from django.utils.text import slugify
from django.core.validators import RegexValidator
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog

class Tenant(models.Model):
    """
    Represents an insurance company (tenant) in the multi-tenant system.
    
    **Key Design Decisions:**
    - Uses 'slug' for URL-safe tenant identification
    - Stores tenant-specific settings as JSON for flexibility
    - Soft delete via 'deleted_at' field
    - Tracks creation and modification timestamps
    """
    
    # Basic Information
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Official name of the insurance company"
    )
    
    slug = models.SlugField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="URL-safe identifier for the tenant"
    )
    
    domain = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$',
                message='Enter a valid domain name',
            ),
        ],
        help_text="Custom domain for this tenant (e.g., tenant.insurance.com)"
    )
    
    # Status and Configuration
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this tenant can access the system"
    )
    
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Tenant-specific configuration (e.g., fleet_policy_enabled, expiry_reminder_days)"
    )
    
    # Contact Information
    contact_email = models.EmailField(
        help_text="Primary contact email for this tenant"
    )
    
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Primary contact phone number"
    )
    
    # Soft Delete Support
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when tenant was soft-deleted"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # History tracking and audit logging for Super Admin actions
    history = HistoricalRecords()
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        indexes = [
            models.Index(fields=['slug', 'is_active']),
            models.Index(fields=['deleted_at']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """
        Override save to auto-generate slug from name if not provided.
        """
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def soft_delete(self):
        """
        Soft delete this tenant.
        Sets deleted_at timestamp and deactivates the tenant.
        """
        from django.utils import timezone
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['deleted_at', 'is_active', 'updated_at'])
    
    def activate(self):
        """Activate this tenant."""
        self.is_active = True
        self.save(update_fields=['is_active', 'updated_at'])
    
    def deactivate(self):
        """Deactivate this tenant (without soft deleting)."""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
    
    @property
    def is_deleted(self):
        """Check if tenant is soft-deleted."""
        return self.deleted_at is not None
    
    def get_setting(self, key, default=None):
        """
        Get a tenant-specific setting value.
        
        Args:
            key: Setting key
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        return self.settings.get(key, default)
    
    def set_setting(self, key, value):
        """
        Set a tenant-specific setting value.
        
        Args:
            key: Setting key
            value: Setting value
        """
        self.settings[key] = value
        self.save(update_fields=['settings', 'updated_at'])


# Register for audit logging
auditlog.register(Tenant)
