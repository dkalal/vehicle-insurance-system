from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from apps.core.models.payment import Payment
from apps.core.models.policy import Policy


@transaction.atomic
def add_payment_and_activate_policy(*, created_by, policy: Policy, amount, payment_method,
                                    reference_number, payer_name="", notes="") -> Payment:
    """
    Register a payment for a policy and activate the policy when fully paid.

    Business rules:
    - Full payment only: total paid must be >= premium_amount to activate; otherwise remain pending.
    - Payments are immutable and audited (handled by model + history/auditlog).
    - Verification workflow: For MVP, we auto-verify upon creation by the staff user.
    """
    if policy is None:
        raise ValidationError({"policy": "Policy is required"})

    # Normalize amounts
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError({"amount": "Payment amount must be positive"})

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

    # MVP: auto-verify by the creator
    payment.verify(verified_by=created_by)

    # If fully paid, attempt activation (policy model enforces business checks)
    if policy.can_activate()[0]:
        policy.activate()

    return payment
