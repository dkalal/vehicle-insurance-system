from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import PasswordResetAudit


@transaction.atomic
def force_reset_password(*, actor, target_user, reason="", ip_address=None) -> str:
    User = get_user_model()

    if not getattr(actor, "is_authenticated", False):
        raise ValidationError({"__all__": "Authentication required."})

    if getattr(actor, "is_super_admin", False):
        raise ValidationError({"__all__": "Super Admin cannot reset tenant user passwords from this interface."})

    if getattr(actor, "tenant_id", None) is None:
        raise ValidationError({"__all__": "Tenant context is required."})

    if getattr(actor, "role", None) != User.ROLE_ADMIN:
        raise ValidationError({"__all__": "Only tenant admins can reset staff passwords."})

    if getattr(target_user, "tenant_id", None) != actor.tenant_id:
        raise ValidationError({"__all__": "You can only reset passwords for users in your tenant."})

    if getattr(target_user, "is_super_admin", False):
        raise ValidationError({"__all__": "Cannot reset password for Super Admin users."})

    temp_password = User.objects.make_random_password()

    target_user.set_password(temp_password)
    target_user.must_change_password = True
    target_user.password_last_reset_at = timezone.now()
    target_user.save(update_fields=["password", "must_change_password", "password_last_reset_at", "updated_at"])

    PasswordResetAudit.objects.create(
        tenant_id=actor.tenant_id,
        actor=actor,
        target_user=target_user,
        reason=(reason or "").strip(),
        ip_address=ip_address or "",
    )

    return temp_password


@transaction.atomic
def super_admin_force_reset_password(*, actor, target_user, reason="", ip_address=None) -> str:
    """Allow Super Admin to reset a tenant user's password across tenants.

    Audit is recorded against the target user's tenant.
    """
    User = get_user_model()

    if not getattr(actor, "is_authenticated", False):
        raise ValidationError({"__all__": "Authentication required."})

    if not getattr(actor, "is_super_admin", False):
        raise ValidationError({"__all__": "Only Super Admin can use this action."})

    # Only tenant-bound users can be reset via this function
    if getattr(target_user, "tenant_id", None) is None:
        raise ValidationError({"__all__": "Target user must belong to a tenant."})

    if getattr(target_user, "is_super_admin", False):
        raise ValidationError({"__all__": "Cannot reset password for Super Admin users from this interface."})

    temp_password = User.objects.make_random_password()

    target_user.set_password(temp_password)
    target_user.must_change_password = True
    target_user.password_last_reset_at = timezone.now()
    target_user.save(update_fields=["password", "must_change_password", "password_last_reset_at", "updated_at"])

    PasswordResetAudit.objects.create(
        tenant_id=target_user.tenant_id,
        actor=actor,
        target_user=target_user,
        reason=(reason or "").strip(),
        ip_address=ip_address or "",
    )

    return temp_password
