from django.core.exceptions import PermissionDenied, ValidationError

from apps.core.models.vehicle import Vehicle


def get_allowed_vehicle_types_for_user(user):
    if user is None:
        return set()
    if getattr(user, 'is_super_admin', False):
        return set()
    if getattr(user, 'tenant_id', None) is None:
        return set()
    return set(user.get_allowed_vehicle_types())


def filter_vehicle_queryset_for_user(*, user, queryset):
    allowed = get_allowed_vehicle_types_for_user(user)
    if not allowed:
        return queryset
    return queryset.filter(vehicle_type__in=allowed)


def ensure_user_can_access_vehicle(*, user, vehicle: Vehicle):
    if vehicle is None:
        raise ValidationError({'vehicle': 'Vehicle is required'})
    if getattr(user, 'tenant_id', None) != getattr(vehicle, 'tenant_id', None):
        raise PermissionDenied('Vehicle does not belong to your tenant')
    allowed = get_allowed_vehicle_types_for_user(user)
    if allowed and vehicle.vehicle_type not in allowed:
        raise PermissionDenied('You are not allowed to manage this vehicle type')


def ensure_user_can_use_vehicle_type(*, user, vehicle_type: str):
    allowed = get_allowed_vehicle_types_for_user(user)
    if allowed and vehicle_type not in allowed:
        raise ValidationError({'vehicle_type': 'You are not allowed to use this vehicle type'})
