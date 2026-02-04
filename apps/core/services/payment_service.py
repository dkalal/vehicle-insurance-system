from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from apps.core.models.payment import Payment
from apps.core.models.policy import Policy


@transaction.atomic
def record_payment(*, created_by, policy: Policy, amount, payment_method,
                 reference_number, payer_name="", notes="") -> Payment:
    """
    Record a payment without verifying it.

    Returns a Payment with is_verified=False.
    """
    if policy is None:
        raise ValidationError({"policy": "Policy is required"})

    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError({"amount": "Payment amount must be positive"})

    # Enforce business rule: full payment only, no partials or overpayments
    premium = policy.premium_amount
    if amount != premium:
        raise ValidationError({
            "amount": f"Payment amount must equal the policy premium ({premium}). Partial or excess payments are not allowed.",
        })

    # Payments are only allowed while policy is pending payment
    if policy.status != Policy.STATUS_PENDING_PAYMENT:
        raise ValidationError({
            "policy": "Payments can only be recorded for policies that are pending payment.",
        })

    # Prevent multiple active payments for the same policy
    # Allow new payments only if all existing ones are explicitly rejected.
    from django.db.models import Q
    existing_non_rejected = Payment.objects.filter(
        tenant=policy.tenant,
        policy=policy,
        deleted_at__isnull=True,
    ).exclude(notes__istartswith='[REJECTED')

    if existing_non_rejected.exists():
        raise ValidationError({
            "__all__": "A payment already exists for this policy. Reject the previous payment before recording a new one.",
        })

    payment = Payment(
        policy=policy,
        tenant=policy.tenant,
        amount=amount,
        payment_date=timezone.now(),
        payment_method=payment_method,
        reference_number=str(reference_number).strip(),
        payer_name=(payer_name or "").strip(),
        notes=(notes or "").strip(),
        created_by=created_by,
        updated_by=created_by,
    )
    payment.full_clean()
    payment.save()
    return payment


@transaction.atomic
def verify_payment(*, verified_by, payment: Payment) -> Payment:
    """
    Verify a payment and activate the policy if fully paid.

    Enforces tenant and role checks.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if payment.tenant_id != getattr(verified_by, 'tenant_id', None):
        raise ValidationError({"__all__": "You cannot verify payments outside your tenant."})

    if payment.is_verified:
        return payment

    if getattr(verified_by, 'role', None) not in (User.ROLE_ADMIN, User.ROLE_MANAGER):
        raise ValidationError({"__all__": "You are not allowed to verify payments."})

    # Enforce full-payment rule at verification time as a safety net
    policy = payment.policy
    if payment.amount != policy.premium_amount:
        raise ValidationError({
            "__all__": "Cannot verify this payment because it does not match the policy premium. Reject it and record the correct full payment.",
        })

    payment.verify(verified_by=verified_by)
    from apps.core.services import policy_service
    policy_service.activate_policy(policy_id=payment.policy_id, actor=verified_by)
    return payment


@transaction.atomic
def add_payment_and_activate_policy(*, created_by, policy: Policy, amount, payment_method,
                                    reference_number, payer_name="", notes="") -> Payment:
    """
    Record and immediately verify a payment (for admins/managers).

    This is a convenience wrapper combining record + verify.
    """
    payment = record_payment(
        created_by=created_by,
        policy=policy,
        amount=amount,
        payment_method=payment_method,
        reference_number=reference_number,
        payer_name=payer_name,
        notes=notes,
    )
    verify_payment(verified_by=created_by, payment=payment)
    return payment
