"""
Unified lifecycle management for compliance artifacts (Policies & Permits).

This service enforces immutability, state transitions, and audit requirements
for all time-bound compliance records.
"""

from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from apps.core.models.policy import Policy
from apps.core.models.vehicle_record import VehiclePermit, LATRARecord


def _validate_actor_permission(actor, entity):
    """Validate actor has permission to modify entity."""
    if not actor:
        raise PermissionDenied("Actor is required")
    
    if not hasattr(actor, 'tenant_id'):
        raise PermissionDenied("Actor must be a tenant user")
    
    entity_tenant_id = getattr(entity, 'tenant_id', None)
    if actor.tenant_id != entity_tenant_id:
        raise PermissionDenied("Actor must belong to the same tenant")
    
    # Super Admin cannot modify business data
    if getattr(actor, 'is_super_admin', False):
        raise PermissionDenied("Super Admin cannot modify compliance data")
    
    # Check role permissions
    role = getattr(actor, 'role', None)
    if role not in ('admin', 'manager'):
        raise PermissionDenied("Only Admin or Manager can cancel compliance records")


def _validate_cancellable(entity):
    """Validate entity can be cancelled."""
    status = getattr(entity, 'status', None)
    
    if status == 'cancelled':
        raise ValidationError("Record is already cancelled")
    
    if status == 'expired':
        raise ValidationError("Cannot cancel expired record")


def _check_vehicle_overlap(entity, model_class):
    """Check for overlapping active records on same vehicle."""
    if entity.status != 'active':
        return
    
    vehicle = entity.vehicle
    tenant = entity.tenant
    
    qs = model_class._base_manager.filter(
        tenant=tenant,
        vehicle=vehicle,
        status='active',
        deleted_at__isnull=True,
    ).exclude(pk=entity.pk)
    
    # For policies: no overlap at all
    if model_class == Policy:
        if qs.exists():
            raise ValidationError("Vehicle already has an active policy")
    
    # For permits: check by permit_type
    if model_class == VehiclePermit:
        permit_type = getattr(entity, 'permit_type', None)
        if permit_type:
            same_type = qs.filter(permit_type=permit_type)
            if same_type.exists():
                raise ValidationError(f"Vehicle already has an active {permit_type.name} permit")


@transaction.atomic
def activate_entity(entity_id, actor, model_class):
    """
    Activate a compliance entity (Policy or Permit).
    
    Rules:
    - Only draft entities can be activated
    - Policy requires full payment
    - No overlapping active records per vehicle
    - Records become immutable after activation
    
    Args:
        entity_id: Entity primary key
        actor: User performing activation
        model_class: Policy, VehiclePermit, or LATRARecord
    
    Returns:
        Activated entity
    """
    entity = model_class._base_manager.select_for_update().get(
        pk=entity_id,
        deleted_at__isnull=True
    )
    
    _validate_actor_permission(actor, entity)
    
    if entity.status == 'active':
        raise ValidationError("Record is already active")
    
    if entity.status not in ('draft', 'pending_payment'):
        raise ValidationError(f"Cannot activate record with status: {entity.status}")
    
    # Policy-specific: check payment
    if model_class == Policy:
        if not entity.is_fully_paid():
            raise ValidationError("Policy must be fully paid before activation")
    
    # Check for overlaps
    _check_vehicle_overlap(entity, model_class)
    
    # Activate
    entity.status = 'active'
    entity.activated_at = timezone.now()
    entity.updated_by = actor
    entity.full_clean()
    entity.save(update_fields=['status', 'activated_at', 'updated_by', 'updated_at'])
    
    return entity


@transaction.atomic
def cancel_entity(entity_id, actor, reason, note, model_class):
    """
    Cancel a compliance entity (Policy or Permit).
    
    Rules:
    - Only Admin/Manager can cancel
    - Reason is mandatory
    - Cancellation is permanent and audited
    - Historical active period is preserved
    
    Args:
        entity_id: Entity primary key
        actor: User performing cancellation
        reason: Cancellation reason (from CANCELLATION_REASON_CHOICES)
        note: Optional additional details
        model_class: Policy, VehiclePermit, or LATRARecord
    
    Returns:
        Cancelled entity
    """
    entity = model_class._base_manager.select_for_update().get(
        pk=entity_id,
        deleted_at__isnull=True
    )
    
    _validate_actor_permission(actor, entity)
    _validate_cancellable(entity)
    
    if not reason:
        raise ValidationError("Cancellation reason is required")
    
    # Validate reason is valid
    valid_reasons = [choice[0] for choice in entity.CANCELLATION_REASON_CHOICES]
    if reason not in valid_reasons:
        raise ValidationError(f"Invalid cancellation reason: {reason}")
    
    # Cancel
    entity.status = 'cancelled'
    entity.cancelled_at = timezone.now()
    entity.cancelled_by = actor
    entity.cancellation_reason = reason
    entity.cancellation_note = (note or '').strip()
    entity.updated_by = actor
    
    entity.save(update_fields=[
        'status', 'cancelled_at', 'cancelled_by', 
        'cancellation_reason', 'cancellation_note',
        'updated_by', 'updated_at'
    ])
    
    return entity


@transaction.atomic
def expire_entity(entity_id, model_class):
    """
    Mark entity as expired (background job use).
    
    Args:
        entity_id: Entity primary key
        model_class: Policy, VehiclePermit, or LATRARecord
    
    Returns:
        Expired entity
    """
    entity = model_class._base_manager.select_for_update().get(
        pk=entity_id,
        deleted_at__isnull=True
    )
    
    if entity.status != 'active':
        raise ValidationError("Only active records can be expired")
    
    if not entity.end_date:
        raise ValidationError("Cannot expire record without end_date")
    
    from datetime import date
    if entity.end_date >= date.today():
        raise ValidationError("Cannot expire record before end_date")
    
    entity.status = 'expired'
    entity.save(update_fields=['status', 'updated_at'])
    
    return entity


def get_active_window(entity):
    """
    Get the active time window for a compliance entity.
    
    Returns:
        Tuple: (start_datetime, end_datetime_or_none)
    """
    if entity.status != 'active' and not entity.activated_at:
        return None, None
    
    start = entity.activated_at or timezone.now()
    
    # If cancelled, active window ends at cancellation
    if entity.status == 'cancelled' and entity.cancelled_at:
        return start, entity.cancelled_at
    
    # If expired, active window ends at end_date
    if entity.status == 'expired' and entity.end_date:
        from datetime import datetime, time
        end_dt = datetime.combine(entity.end_date, time.max)
        return start, timezone.make_aware(end_dt)
    
    # Still active
    if entity.status == 'active':
        return start, None
    
    return None, None


def is_active_at(entity, check_date):
    """
    Check if entity was active at a specific date.
    
    Args:
        entity: Policy or Permit instance
        check_date: Date to check
    
    Returns:
        Boolean
    """
    start, end = get_active_window(entity)
    
    if not start:
        return False
    
    from datetime import datetime, time
    check_dt = datetime.combine(check_date, time.min)
    check_dt = timezone.make_aware(check_dt)
    
    if check_dt < start:
        return False
    
    if end and check_dt > end:
        return False
    
    return True
