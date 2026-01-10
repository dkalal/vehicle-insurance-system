"""
Base abstract models for the Vehicle Insurance system.

These models provide common functionality for all domain models:
- Tenant awareness
- Soft delete support
- Audit tracking (who created/modified)
- Timestamps
"""

from django.db import models
from django.conf import settings
from apps.tenants.managers import TenantAwareSoftDeleteManager
from apps.tenants.context import get_current_tenant


class TenantAwareModel(models.Model):
    """
    Abstract base model for tenant-scoped entities.
    
    **Why this pattern:**
    - Ensures ALL business data is scoped to a tenant
    - Prevents accidental cross-tenant data leakage
    - Automatically sets tenant on save
    
    **Usage:**
    ```python
    class Customer(TenantAwareModel):
        name = models.CharField(max_length=255)
    ```
    
    The tenant field is automatically populated from request context.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,  # Prevent deletion of tenant with data
        related_name='%(class)s_set',  # Dynamic related name
        db_index=True,
        help_text="Insurance company this record belongs to"
    )
    
    class Meta:
        abstract = True
        # Every tenant-aware model gets an index on tenant
        indexes = [
            models.Index(fields=['tenant']),
        ]
    
    def save(self, *args, **kwargs):
        """
        Override save to automatically set tenant from context.
        """
        if not self.tenant_id:
            tenant = get_current_tenant()
            if tenant:
                self.tenant = tenant
            elif not kwargs.get('force_insert'):
                # Allow explicit tenant assignment in tests/migrations
                raise ValueError(
                    f"Cannot save {self.__class__.__name__} without a tenant. "
                    f"Set request context or assign tenant explicitly."
                )
        super().save(*args, **kwargs)


class AuditableModel(models.Model):
    """
    Abstract base model for audit tracking.
    
    **Why this matters:**
    - Insurance is regulated - we need to know who changed what
    - Compliance requirements (GDPR, insurance regulations)
    - Dispute resolution
    
    **Tracks:**
    - Who created the record
    - When it was created
    - Who last modified it
    - When it was last modified
    """
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created_set',
        help_text="User who created this record"
    )
    
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated_set',
        help_text="User who last updated this record"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]


class SoftDeleteModel(models.Model):
    """
    Abstract base model for soft delete support.
    
    **Why soft delete:**
    - Insurance data must be preserved for legal/compliance
    - No accidental data loss
    - Ability to recover from mistakes
    - Historical integrity
    
    **How it works:**
    - Instead of DELETE, we set deleted_at timestamp
    - Default manager filters out deleted records
    - Special manager methods to access deleted records
    """
    
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when record was soft-deleted"
    )
    
    # Use the combined tenant-aware soft-delete manager
    objects = TenantAwareSoftDeleteManager()
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['deleted_at']),
        ]
    
    def soft_delete(self):
        """
        Soft delete this record.
        Sets deleted_at to current time.
        """
        from django.utils import timezone
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])
    
    def restore(self):
        """
        Restore a soft-deleted record.
        Clears deleted_at timestamp.
        """
        self.deleted_at = None
        self.save(update_fields=['deleted_at'])
    
    @property
    def is_deleted(self):
        """Check if record is soft-deleted."""
        return self.deleted_at is not None


class BaseModel(TenantAwareModel, AuditableModel, SoftDeleteModel):
    """
    Ultimate base model combining all common functionality.
    
    **Features:**
    - Tenant-aware
    - Audit tracking
    - Soft delete
    - Automatic timestamps
    
    **Usage:**
    Most domain models should inherit from this:
    ```python
    class Customer(BaseModel):
        name = models.CharField(max_length=255)
    ```
    
    This gives you tenant isolation, audit trail, soft delete for free.
    """
    
    class Meta:
        abstract = True
