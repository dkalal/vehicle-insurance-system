from django.db import transaction
from django.core.exceptions import ValidationError

from apps.core.models.vehicle import Vehicle
from apps.core.models.vehicle_record import LATRARecord


@transaction.atomic
def create_latra_record(*, created_by, vehicle: Vehicle, latra_number: str,
                        license_type: str, start_date, end_date=None, route: str = "") -> LATRARecord:
    if vehicle is None:
        raise ValidationError({"vehicle": "Vehicle is required"})

    if getattr(created_by, "tenant_id", None) != getattr(vehicle, "tenant_id", None):
        raise ValidationError({"vehicle": "Vehicle must belong to your tenant"})

    tenant = vehicle.tenant

    # Optional: prevent duplicate LATRA number within tenant while active
    existing_same_number = LATRARecord.objects.filter(
        tenant=tenant,
        latra_number=latra_number.strip(),
        deleted_at__isnull=True,
    )
    if existing_same_number.exists():
        raise ValidationError({"latra_number": "A LATRA record with this number already exists for your tenant"})

    obj = LATRARecord(
        tenant=tenant,
        vehicle=vehicle,
        latra_number=latra_number.strip(),
        license_type=license_type.strip(),
        route=(route or "").strip(),
        start_date=start_date,
        end_date=end_date,
        status=LATRARecord.STATUS_ACTIVE,
        created_by=created_by,
        updated_by=created_by,
    )

    # Enforce no overlapping ACTIVE records for same vehicle + license_type
    _assert_no_overlapping_active_latra(obj)

    obj.full_clean()
    obj.save()
    return obj


@transaction.atomic
def update_latra_record(*, updated_by, record: LATRARecord, **fields) -> LATRARecord:
    if record is None:
        raise ValidationError({"record": "LATRA record is required"})
    if getattr(updated_by, "tenant_id", None) != getattr(record, "tenant_id", None):
        raise ValidationError({"record": "LATRA record must belong to your tenant"})

    for name in [
        "latra_number",
        "license_type",
        "route",
        "start_date",
        "end_date",
        "status",
    ]:
        if name in fields and fields[name] is not None:
            value = fields[name]
            if isinstance(value, str):
                value = value.strip()
            setattr(record, name, value)

    # Re-run overlap checks if record remains active
    _assert_no_overlapping_active_latra(record)

    record.updated_by = updated_by
    record.full_clean()
    record.save()
    return record


@transaction.atomic
def soft_delete_latra_record(*, deleted_by, record: LATRARecord) -> LATRARecord:
    if record is None:
        raise ValidationError({"record": "LATRA record is required"})
    if getattr(deleted_by, "tenant_id", None) != getattr(record, "tenant_id", None):
        raise ValidationError({"record": "LATRA record must belong to your tenant"})

    record.updated_by = deleted_by
    record.save(update_fields=["updated_by"])
    record.soft_delete()
    return record


def _assert_no_overlapping_active_latra(candidate: LATRARecord) -> None:
    """Ensure there is no other ACTIVE LATRA record with overlapping period
    for the same vehicle + license_type.
    """
    if candidate.status != LATRARecord.STATUS_ACTIVE:
        return

    start = candidate.start_date
    end = candidate.end_date

    qs = LATRARecord.objects.filter(
        tenant=candidate.tenant,
        vehicle=candidate.vehicle,
        license_type=candidate.license_type,
        status=LATRARecord.STATUS_ACTIVE,
        deleted_at__isnull=True,
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
            "__all__": "Overlapping active LATRA records for this vehicle and license type are not allowed",
        })
