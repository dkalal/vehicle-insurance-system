"""
Vehicle model for the Vehicle Insurance system.

Represents vehicles owned by customers and covered by policies.
"""

from django.db import models
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog
from .base import BaseModel


class Vehicle(BaseModel):
    """
    Vehicle owned by a customer.
    
    **Business Rules:**
    - Vehicle types: motorcycle, bajaji (three-wheeler), car
    - Belongs to ONE customer at a time
    - Can have multiple policies over time
    - CANNOT have more than ONE active policy at any moment
    - Registration number must be unique per tenant
    - Full history tracked
    - Compliance status computed from insurance and permits
    """
    
    VEHICLE_TYPE_MOTORCYCLE = 'motorcycle'
    VEHICLE_TYPE_BAJAJI = 'bajaji'
    VEHICLE_TYPE_CAR = 'car'
    
    VEHICLE_TYPE_CHOICES = [
        (VEHICLE_TYPE_MOTORCYCLE, 'Motorcycle'),
        (VEHICLE_TYPE_BAJAJI, 'Bajaji (Three-Wheeler)'),
        (VEHICLE_TYPE_CAR, 'Car'),
    ]
    
    # Basic Information
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        db_index=True,
        help_text="Type of vehicle"
    )
    
    # Owner
    owner = models.ForeignKey(
        'Customer',
        on_delete=models.PROTECT,
        related_name='vehicles',
        help_text="Current owner of this vehicle"
    )
    
    # Registration
    registration_number = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Vehicle registration/license plate number"
    )
    
    # Vehicle Details
    make = models.CharField(
        max_length=100,
        help_text="Vehicle manufacturer (e.g., Toyota, Honda)"
    )
    
    model = models.CharField(
        max_length=100,
        help_text="Vehicle model"
    )
    
    year = models.PositiveIntegerField(
        help_text="Year of manufacture"
    )
    
    color = models.CharField(
        max_length=50,
        blank=True,
        help_text="Vehicle color"
    )
    
    # Identification Numbers
    chassis_number = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Vehicle chassis number (VIN)"
    )
    
    engine_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Engine number"
    )
    
    # Additional Details
    seating_capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of seats"
    )
    
    engine_capacity = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Engine capacity in CC (e.g., 1500.00)"
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the vehicle"
    )
    
    # History Tracking
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = 'Vehicle'
        verbose_name_plural = 'Vehicles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'registration_number']),
            models.Index(fields=['tenant', 'owner']),
            models.Index(fields=['tenant', 'vehicle_type']),
            models.Index(fields=['chassis_number']),
        ]
        constraints = [
            # Unique registration number per tenant
            models.UniqueConstraint(
                fields=['tenant', 'registration_number'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_registration_per_tenant'
            ),
        ]
    
    def __str__(self):
        return f"{self.make} {self.model} ({self.registration_number})"
    
    def get_active_policy(self):
        """
        Get the currently active policy for this vehicle.
        
        Returns:
            Active Policy instance or None.
        """
        from .policy import Policy
        return Policy._base_manager.filter(
            tenant=self.tenant,
            deleted_at__isnull=True,
            vehicle=self,
            status=Policy.STATUS_ACTIVE,
        ).first()
    
    def has_active_policy(self):
        """
        Check if vehicle has an active policy.
        
        Returns:
            Boolean indicating if vehicle has active policy.
        """
        return self.get_active_policy() is not None
    
    def can_create_new_policy(self):
        """
        Check if a new policy can be created for this vehicle.
        
        Business Rule: Vehicle cannot have more than one active policy.
        
        Returns:
            Boolean indicating if new policy can be created.
        """
        return not self.has_active_policy()
    
    def get_compliance_status(self, risk_window_days=30):
        """
        Get real-time compliance status for this vehicle.
        
        Args:
            risk_window_days: Days before expiry to consider 'at risk'
            
        Returns:
            String: 'compliant', 'at_risk', or 'non_compliant'
        """
        from apps.core.services.vehicle_compliance_service import VehicleComplianceService
        result = VehicleComplianceService.compute_compliance_status(
            vehicle=self,
            risk_window_days=risk_window_days
        )
        return result['status']
    
    def is_compliant(self, risk_window_days=30):
        """
        Check if vehicle is fully compliant.
        
        Returns:
            Boolean indicating if vehicle is compliant.
        """
        from apps.core.services.vehicle_compliance_service import VehicleComplianceService
        return self.get_compliance_status(risk_window_days) == VehicleComplianceService.STATUS_COMPLIANT
    
    def transfer_ownership(self, new_owner):
        """
        Transfer ownership of vehicle to a new customer.
        
        Args:
            new_owner: Customer instance.
            
        Note:
            This is tracked in history.
        """
        self.owner = new_owner
        self.save(update_fields=['owner', 'updated_at'])


# Register for audit logging
auditlog.register(Vehicle)
