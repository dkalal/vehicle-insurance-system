from django.db import transaction
from django.core.exceptions import ValidationError

from apps.core.models.vehicle_record import PermitType


@transaction.atomic
def create_permit_type(*, created_by, name: str, is_active: bool = True, conflicts_with=None) -> PermitType:
    """Create a tenant-scoped permit type.

    - Scoped to creator's tenant
    - Super Admin cannot create tenant permit types from dashboard
    - Enforces per-tenant uniqueness on name (model constraint will validate)
    """
    tenant = getattr(created_by, "tenant", None)
    if tenant is None or getattr(created_by, "is_super_admin", False):
        raise ValidationError({"__all__": "Only tenant users can create permit types."})

    pt = PermitType(
        tenant=tenant,
        name=(name or "").strip(),
        is_active=bool(is_active),
    )
    pt.full_clean()
    pt.save()

    if conflicts_with:
        pt.conflicts_with.set(conflicts_with)
    return pt


@transaction.atomic
def update_permit_type(*, updated_by, permit_type: PermitType, name: str, is_active: bool = True, conflicts_with=None) -> PermitType:
    if permit_type is None:
        raise ValidationError({"__all__": "Permit type is required."})

    tenant_id = getattr(updated_by, "tenant_id", None)
    if tenant_id is None or tenant_id != getattr(permit_type, "tenant_id", None):
        raise ValidationError({"__all__": "You can only modify permit types in your tenant."})
    if getattr(updated_by, "is_super_admin", False):
        raise ValidationError({"__all__": "Super Admin cannot modify tenant permit types from dashboard."})

    permit_type.name = (name or "").strip()
    permit_type.is_active = bool(is_active)
    permit_type.full_clean()
    permit_type.save()

    if conflicts_with is not None:
        permit_type.conflicts_with.set(conflicts_with)

    return permit_type
