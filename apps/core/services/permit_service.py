from django.db import transaction
from django.core.exceptions import ValidationError

from apps.core.models.vehicle import Vehicle
from apps.core.models.vehicle_record import PermitType, VehiclePermit
from . import lifecycle_service


@transaction.atomic
def create_vehicle_permit(*, created_by, vehicle: Vehicle, permit_type: PermitType,
                          reference_number: str, start_date, end_date=None, document=None) -> VehiclePermit:
    if vehicle is None:
        raise ValidationError({"vehicle": "Vehicle is required"})
    if permit_type is None:
        raise ValidationError({"permit_type": "Permit type is required"})

    if getattr(created_by, "tenant_id", None) != getattr(vehicle, "tenant_id", None):
        raise ValidationError({"vehicle": "Vehicle must belong to your tenant"})
    if getattr(vehicle, "tenant_id", None) != getattr(permit_type, "tenant_id", None):
        raise ValidationError({"permit_type": "Permit type must belong to your tenant"})

    tenant = vehicle.tenant

    obj = VehiclePermit(
        tenant=tenant,
        vehicle=vehicle,
        permit_type=permit_type,
        reference_number=reference_number.strip(),
        start_date=start_date,
        end_date=end_date,
        status=VehiclePermit.STATUS_DRAFT,
        created_by=created_by,
        updated_by=created_by,
        document=document,
    )

    obj.full_clean()
    obj.save()
    return obj


@transaction.atomic
def activate_permit(*, permit_id, actor):
    """Activate a permit using unified lifecycle service."""
    permit = VehiclePermit._base_manager.get(pk=permit_id, deleted_at__isnull=True)
    _assert_no_conflicting_active_permits(permit, check_active=True)
    return lifecycle_service.activate_entity(permit_id, actor, VehiclePermit)


@transaction.atomic
def cancel_permit(*, permit_id, actor, reason, note=""):
    """Cancel a permit using unified lifecycle service."""
    return lifecycle_service.cancel_entity(permit_id, actor, reason, note, VehiclePermit)


@transaction.atomic
def update_vehicle_permit(*, updated_by, permit: VehiclePermit, **fields) -> VehiclePermit:
    """Update permit (only if not immutable)."""
    if permit is None:
        raise ValidationError({"permit": "Permit is required"})
    if getattr(updated_by, "tenant_id", None) != getattr(permit, "tenant_id", None):
        raise ValidationError({"permit": "Permit must belong to your tenant"})
    
    if permit.is_immutable():
        raise ValidationError({"__all__": "Cannot edit active permit. Cancel and create new one."})

    for name in [
        "permit_type",
        "reference_number",
        "start_date",
        "end_date",
    ]:
        if name in fields and fields[name] is not None:
            value = fields[name]
            if isinstance(value, str):
                value = value.strip()
            setattr(permit, name, value)

    permit.updated_by = updated_by
    permit.full_clean()
    permit.save()
    return permit


def _assert_no_conflicting_active_permits(candidate: VehiclePermit, check_active=False) -> None:
    """Enforce permit conflict rules.

    A vehicle cannot have overlapping ACTIVE permits where the permit types
    conflict with each other.

    When ``check_active`` is True (used during activation), we evaluate
    conflicts as if the candidate were active, even if its current status is
    still ``draft``.
    """
    if not check_active and candidate.status != VehiclePermit.STATUS_ACTIVE:
        return

    start = candidate.start_date
    end = candidate.end_date

    # Determine conflicting permit types (both directions in the M2M)
    conflicts_a = candidate.permit_type.conflicts_with.all()
    conflicts_b = PermitType.objects.filter(conflicts_with=candidate.permit_type)

    conflicting_types = set(conflicts_a) | set(conflicts_b)
    if not conflicting_types:
        return

    qs = VehiclePermit.objects.filter(
        tenant=candidate.tenant,
        vehicle=candidate.vehicle,
        status=VehiclePermit.STATUS_ACTIVE,
        deleted_at__isnull=True,
        permit_type__in=[pt.pk for pt in conflicting_types],
    )
    if candidate.pk:
        qs = qs.exclude(pk=candidate.pk)

    from django.db.models import Q

    # Two intervals [s1, e1] and [s2, e2] overlap if:
    #   s1 <= e2 (or e2 is open-ended) AND s2 <= e1 (or e1 is open-ended).
    if end is None:
        # Candidate is open-ended from `start` onward
        overlap_q = Q(end_date__isnull=True) | Q(end_date__gte=start)
    else:
        overlap_q = Q(start_date__lte=end) & (Q(end_date__isnull=True) | Q(end_date__gte=start))

    if qs.filter(overlap_q).exists():
        raise ValidationError({
            "__all__": "Conflicting active permits for this vehicle are not allowed in the selected period",
        })
