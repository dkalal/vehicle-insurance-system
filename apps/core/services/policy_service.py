from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from apps.core.models.policy import Policy
from apps.core.models.vehicle import Vehicle


@transaction.atomic
def create_policy(*, created_by, vehicle: Vehicle, start_date, end_date,
                  premium_amount, coverage_amount=None, policy_type="", notes="") -> Policy:
    """
    Create a policy in draft or pending_payment state for a vehicle.

    Rules:
    - Policy number auto-generated per tenant.
    - End date must be after start date (DB constraint also enforces).
    - Vehicle may have only one active policy; creation starts as draft unless caller later activates after payment.
    """
    if vehicle is None:
        raise ValidationError({"vehicle": "Vehicle is required"})

    tenant = getattr(vehicle, "tenant", None)
    if tenant is None:
        raise ValidationError({"vehicle": "Vehicle must belong to a tenant"})

    policy = Policy(
        vehicle=vehicle,
        tenant=tenant,
        start_date=start_date,
        end_date=end_date,
        premium_amount=Decimal(premium_amount),
        coverage_amount=Decimal(coverage_amount) if coverage_amount is not None else None,
        policy_type=(policy_type or "").strip(),
        notes=(notes or "").strip(),
        status=Policy.STATUS_PENDING_PAYMENT,
        created_by=created_by,
        updated_by=created_by,
    )
    # Generate policy number using tenant context
    policy.policy_number = Policy.generate_policy_number(tenant)

    policy.full_clean()
    policy.save()
    return policy


@transaction.atomic
def renew_policy(*, created_by, existing_policy: Policy, new_start_date, new_end_date,
                 new_premium_amount, notes="") -> Policy:
    """
    Renew a policy by creating a new policy record for the same vehicle with the new dates.
    The new policy starts in pending_payment; activation occurs after full payment.
    """
    if existing_policy is None:
        raise ValidationError({"existing_policy": "Existing policy is required"})

    return create_policy(
        created_by=created_by,
        vehicle=existing_policy.vehicle,
        start_date=new_start_date,
        end_date=new_end_date,
        premium_amount=new_premium_amount,
        coverage_amount=existing_policy.coverage_amount,
        policy_type=existing_policy.policy_type,
        notes=notes or f"Renewal of {existing_policy.policy_number}",
    )
