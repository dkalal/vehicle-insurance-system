"""
Custom User model with multi-tenancy support.

This is the central authentication model for the system, supporting both
tenant users (Admin, Manager, Agent) and Super Admin (platform owner).
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    
    **Key Features:**
    - Multi-tenancy support via foreign key to Tenant
    - Role-based access (Admin, Manager, Agent)
    - Super Admin support (tenant=NULL)
    - History tracking for compliance
    
    **Business Rules:**
    - Super Admin: is_super_admin=True AND tenant=NULL
    - Regular User: is_super_admin=False AND tenant=NOT NULL
    - A user CANNOT be both Super Admin and have a tenant
    """
    
    # Role choices for tenant users
    ROLE_ADMIN = 'admin'
    ROLE_MANAGER = 'manager'
    ROLE_AGENT = 'agent'
    
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MANAGER, 'Manager'),
        (ROLE_AGENT, 'Agent/Staff'),
    ]
    
    # Multi-tenancy relationship
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users',
        help_text="Insurance company this user belongs to (NULL for Super Admin)"
    )
    
    # Super Admin flag
    is_super_admin = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Platform owner with access to all tenants (tenant must be NULL)"
    )
    
    # Role for tenant users
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        null=True,
        blank=True,
        help_text="Role within tenant organization (required for tenant users)"
    )
    
    # Additional profile fields
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact phone number"
    )
    
    # Status flags
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether this user should be treated as active"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    must_change_password = models.BooleanField(
        default=False,
        db_index=True,
        help_text="If true, user must set a new password before accessing the dashboard",
    )

    password_last_reset_at = models.DateTimeField(null=True, blank=True)
    
    # History tracking
    history = HistoricalRecords()
    
    class Meta:
        ordering = ['username']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['is_super_admin']),
            models.Index(fields=['email']),
        ]
        constraints = [
            # Ensure Super Admin has no tenant
            models.CheckConstraint(
                check=(
                    models.Q(is_super_admin=True, tenant__isnull=True) |
                    models.Q(is_super_admin=False)
                ),
                name='super_admin_no_tenant'
            ),
            # Ensure tenant users have a role
            models.CheckConstraint(
                check=(
                    models.Q(tenant__isnull=False, role__isnull=False) |
                    models.Q(tenant__isnull=True)
                ),
                name='tenant_user_has_role'
            ),
        ]
    
    def __str__(self):
        if self.is_super_admin:
            return f"{self.get_full_name() or self.username} (Super Admin)"
        return f"{self.get_full_name() or self.username} - {self.tenant.name if self.tenant else 'No Tenant'}"
    
    def clean(self):
        """
        Validate user instance before saving.
        """
        super().clean()
        
        # Rule 1: Super Admin must have tenant=NULL
        if self.is_super_admin and self.tenant:
            raise ValidationError({
                'tenant': 'Super Admin cannot be assigned to a tenant.'
            })
        
        # Rule 2: Tenant users must have a tenant
        if not self.is_super_admin and not self.tenant:
            raise ValidationError({
                'tenant': 'Regular users must be assigned to a tenant.'
            })
        
        # Rule 3: Tenant users must have a role
        if self.tenant and not self.role:
            raise ValidationError({
                'role': 'Tenant users must have a role assigned.'
            })
        
        # Rule 4: Super Admin should not have a role
        if self.is_super_admin and self.role:
            raise ValidationError({
                'role': 'Super Admin should not have a tenant role.'
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to enforce business rules.
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_tenant_admin(self):
        """Check if user is a tenant admin."""
        return self.tenant and self.role == self.ROLE_ADMIN
    
    @property
    def is_tenant_manager(self):
        """Check if user is a tenant manager."""
        return self.tenant and self.role == self.ROLE_MANAGER
    
    @property
    def is_tenant_agent(self):
        """Check if user is a tenant agent/staff."""
        return self.tenant and self.role == self.ROLE_AGENT
    
    def has_tenant_permission(self, permission_name):
        """
        Check if user has a specific tenant permission.
        
        Args:
            permission_name: Permission name to check.
            
        Returns:
            Boolean indicating if user has permission.
        """
        if self.is_super_admin:
            # Super Admin has no tenant permissions
            return False

        if not self.tenant or not self.tenant.is_active:
            return False

        # Permission hierarchy: Admin > Manager > Agent
        if self.is_tenant_admin:
            return True  # Admins have all permissions

        # Define manager permissions
        manager_permissions = [
            'view_customers', 'view_vehicles', 'view_policies', 'view_payments',
            'view_reports', 'manage_staff'
        ]

        if self.is_tenant_manager and permission_name in manager_permissions:
            return True

        # Agent permissions
        agent_permissions = [
            'view_customers', 'add_customers', 'change_customers',
            'view_vehicles', 'add_vehicles', 'change_vehicles',
            'view_policies', 'add_policies',
            'view_payments', 'add_payments',
        ]

        if self.is_tenant_agent and permission_name in agent_permissions:
            return True

        return False

    def get_allowed_vehicle_types(self):
        if getattr(self, 'is_super_admin', False):
            return set()
        if getattr(self, 'tenant_id', None) is None:
            return set()
        if getattr(self, 'role', None) == self.ROLE_ADMIN:
            from apps.core.models.vehicle import Vehicle
            return {t for (t, _) in Vehicle.VEHICLE_TYPE_CHOICES}
        types = set(
            UserVehicleTypeAssignment.objects.filter(
                tenant_id=self.tenant_id,
                user_id=self.id,
                deleted_at__isnull=True,
            ).values_list('vehicle_type', flat=True)
        )
        if not types:
            from apps.core.models.vehicle import Vehicle
            return {t for (t, _) in Vehicle.VEHICLE_TYPE_CHOICES}
        return types


class UserVehicleTypeAssignment(models.Model):
    """Restrict a tenant staff user's work scope to one or more vehicle types."""

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,
        related_name='user_vehicle_type_assignments',
        db_index=True,
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='vehicle_type_assignments',
        db_index=True,
    )
    vehicle_type = models.CharField(max_length=20, db_index=True)

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_vehicle_type_assignment_created_set',
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_vehicle_type_assignment_updated_set',
    )

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'user', 'vehicle_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'user', 'vehicle_type'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_user_vehicle_type_assignment',
            ),
        ]

    def clean(self):
        super().clean()
        if not self.tenant_id:
            raise ValidationError({'tenant': 'Tenant is required'})
        if not self.user_id:
            raise ValidationError({'user': 'User is required'})
        if self.user and getattr(self.user, 'tenant_id', None) != self.tenant_id:
            raise ValidationError({'user': 'User must belong to the same tenant'})
        from apps.core.models.vehicle import Vehicle
        allowed_types = {t for (t, _) in Vehicle.VEHICLE_TYPE_CHOICES}
        if self.vehicle_type not in allowed_types:
            raise ValidationError({'vehicle_type': 'Invalid vehicle type'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
