from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import UserVehicleTypeAssignment
from apps.core.models.vehicle import Vehicle


@transaction.atomic
def set_user_vehicle_types(*, tenant, user, vehicle_types, updated_by=None):
    if tenant is None or user is None:
        raise ValidationError("Tenant and user are required")
    if getattr(user, 'tenant_id', None) != getattr(tenant, 'id', None):
        raise ValidationError("User must belong to the same tenant")
    if getattr(user, 'is_super_admin', False):
        raise ValidationError("Super Admin cannot be scoped to vehicle types")

    allowed_types = {t for (t, _) in Vehicle.VEHICLE_TYPE_CHOICES}
    vehicle_types = {t for t in (vehicle_types or []) if t in allowed_types}

    # Soft-delete existing assignments
    UserVehicleTypeAssignment.objects.filter(
        tenant=tenant,
        user=user,
        deleted_at__isnull=True,
    ).update(deleted_at=timezone.now(), updated_at=timezone.now(), updated_by=updated_by)

    # Empty set means allow all vehicle types
    if not vehicle_types:
        return []

    assignments = []
    for vt in sorted(vehicle_types):
        assignments.append(
            UserVehicleTypeAssignment(
                tenant=tenant,
                user=user,
                vehicle_type=vt,
                created_by=updated_by,
                updated_by=updated_by,
            )
        )
    UserVehicleTypeAssignment.objects.bulk_create(assignments)
    return assignments


def get_user_vehicle_types(*, tenant, user):
    if tenant is None or user is None:
        return []
    return list(
        UserVehicleTypeAssignment.objects.filter(
            tenant=tenant,
            user=user,
            deleted_at__isnull=True,
        ).values_list('vehicle_type', flat=True)
    )
