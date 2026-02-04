"""
Core domain models package.
"""

# Import base models
from .base import (
    BaseModel,
    TenantAwareModel,
    AuditableModel,
    SoftDeleteModel,
)

# Import domain models
# Note: These imports must be after base imports to avoid circular dependency
from .customer import Customer
from .vehicle import Vehicle
from .policy import Policy
from .payment import Payment
from .support_request import SupportRequest
from .vehicle_record import VehicleRecord, LATRARecord, PermitType, VehiclePermit
from .onboarding import TenantOnboardingState

__all__ = [
    'BaseModel',
    'TenantAwareModel',
    'AuditableModel',
    'SoftDeleteModel',
    'Customer',
    'Vehicle',
    'Policy',
    'Payment',
    'SupportRequest',
    'VehicleRecord',
    'LATRARecord',
    'PermitType',
    'VehiclePermit',
    'TenantOnboardingState',
]
