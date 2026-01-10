from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.models.vehicle import Vehicle
from apps.core.models.customer import Customer


@transaction.atomic
def create_vehicle(*, created_by, owner: Customer, vehicle_type: str,
                   registration_number: str, make: str, model: str, year: int,
                   **kwargs) -> Vehicle:
    """
    Create a vehicle for a given owner, enforcing tenant boundaries.

    Rules:
    - Owner is required and must belong to the same tenant as created_by.
    - Registration number is unique per tenant (DB constraint); we also pre-check to give a nicer error.
    """
    if owner is None:
        raise ValidationError({"owner": "Owner is required"})

    # Tenant boundary enforcement (defense in depth beyond middleware/managers)
    if getattr(created_by, 'tenant_id', None) != getattr(owner, 'tenant_id', None):
        raise ValidationError({"owner": "Owner must belong to your tenant"})

    data = {
        "owner": owner,
        "vehicle_type": vehicle_type,
        "registration_number": registration_number.strip(),
        "make": make.strip(),
        "model": model.strip(),
        "year": int(year),
        "tenant": owner.tenant,
        "created_by": created_by,
        "updated_by": created_by,
        # optionals
        "color": kwargs.get("color", "").strip(),
        "chassis_number": kwargs.get("chassis_number", "").strip(),
        "engine_number": kwargs.get("engine_number", "").strip(),
        "seating_capacity": kwargs.get("seating_capacity"),
        "engine_capacity": kwargs.get("engine_capacity"),
        "notes": kwargs.get("notes", "").strip(),
    }

    # Friendly pre-check for duplicate registration within tenant
    if Vehicle.objects.filter(tenant=owner.tenant, registration_number=data["registration_number"], deleted_at__isnull=True).exists():
        raise ValidationError({"registration_number": "A vehicle with this registration already exists in your tenant"})

    v = Vehicle(**data)
    v.full_clean()
    v.save()
    return v


@transaction.atomic
def update_vehicle(*, updated_by, vehicle: Vehicle, **kwargs) -> Vehicle:
    """
    Update a vehicle; enforce tenant boundaries and uniqueness.
    """
    if vehicle is None:
        raise ValidationError({"vehicle": "Vehicle is required"})
    if getattr(updated_by, 'tenant_id', None) != getattr(vehicle, 'tenant_id', None):
        raise ValidationError({"vehicle": "Vehicle must belong to your tenant"})

    # Capture possible registration change to pre-check duplicates
    new_reg = kwargs.get("registration_number")
    if new_reg is not None:
        reg = str(new_reg).strip()
        if Vehicle.objects.filter(tenant=vehicle.tenant, registration_number=reg, deleted_at__isnull=True).exclude(pk=vehicle.pk).exists():
            raise ValidationError({"registration_number": "A vehicle with this registration already exists in your tenant"})
        vehicle.registration_number = reg

    # Apply other fields if provided
    for f in [
        "owner", "vehicle_type", "make", "model", "year", "color", "chassis_number",
        "engine_number", "seating_capacity", "engine_capacity", "notes",
    ]:
        if f in kwargs and kwargs[f] is not None:
            setattr(vehicle, f, kwargs[f])

    vehicle.updated_by = updated_by
    vehicle.full_clean()
    vehicle.save()
    return vehicle


@transaction.atomic
def soft_delete_vehicle(*, deleted_by, vehicle: Vehicle) -> Vehicle:
    if vehicle is None:
        raise ValidationError({"vehicle": "Vehicle is required"})
    if getattr(deleted_by, 'tenant_id', None) != getattr(vehicle, 'tenant_id', None):
        raise ValidationError({"vehicle": "Vehicle must belong to your tenant"})
    vehicle.updated_by = deleted_by
    vehicle.save(update_fields=['updated_by'])
    vehicle.soft_delete()
    return vehicle
