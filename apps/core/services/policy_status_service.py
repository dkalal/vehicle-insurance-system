from datetime import date

from django.db import models

from apps.core.models.payment import Payment
from apps.core.models.policy import Policy


def reconcile_policy_status(policy: Policy, *, actor=None) -> Policy:
    """Repair stale policy lifecycle states caused by legacy or interrupted flows."""
    if policy is None:
        return policy

    changed_fields = []
    today = date.today()

    if policy.status == Policy.STATUS_ACTIVE and policy.end_date < today:
        policy.status = Policy.STATUS_EXPIRED
        changed_fields.append('status')

    if policy.status == Policy.STATUS_PENDING_PAYMENT and policy.is_fully_paid():
        overlap_exists = (
            Policy._base_manager.filter(
                tenant=policy.tenant,
                deleted_at__isnull=True,
                vehicle=policy.vehicle,
                status=Policy.STATUS_ACTIVE,
                start_date__lte=policy.end_date,
                end_date__gte=policy.start_date,
            )
            .exclude(pk=policy.pk)
            .exists()
        )
        if not overlap_exists:
            verified_payment = (
                Payment._base_manager.filter(
                    tenant=policy.tenant,
                    deleted_at__isnull=True,
                    policy=policy,
                    is_verified=True,
                )
                .order_by('-verified_at', '-payment_date', '-created_at')
                .select_related('verified_by')
                .first()
            )
            policy.status = Policy.STATUS_ACTIVE
            changed_fields.append('status')

            if policy.activated_at is None:
                policy.activated_at = (
                    getattr(verified_payment, 'verified_at', None)
                    or getattr(verified_payment, 'payment_date', None)
                )
                changed_fields.append('activated_at')

            if actor is not None:
                policy.updated_by = actor
                changed_fields.append('updated_by')
            elif getattr(verified_payment, 'verified_by', None) is not None:
                policy.updated_by = verified_payment.verified_by
                changed_fields.append('updated_by')

    if changed_fields:
        changed_fields.append('updated_at')
        policy.save(update_fields=list(dict.fromkeys(changed_fields)))

    return policy


def reconcile_policies(*, tenant=None, vehicle=None, policies=None, actor=None):
    """Reconcile a targeted set of policies so all views read the same status."""
    if policies is None:
        queryset = Policy._base_manager.filter(deleted_at__isnull=True)
        if tenant is not None:
            queryset = queryset.filter(tenant=tenant)
        if vehicle is not None:
            queryset = queryset.filter(vehicle=vehicle)
        queryset = queryset.filter(
            models.Q(status=Policy.STATUS_ACTIVE, end_date__lt=date.today())
            | models.Q(status=Policy.STATUS_PENDING_PAYMENT, payments__is_verified=True)
        ).distinct()
        policies = list(queryset.select_related('vehicle'))
    else:
        policies = list(policies)

    for policy in policies:
        reconcile_policy_status(policy, actor=actor)

    return policies
