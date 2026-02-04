from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction


@transaction.atomic
def update_profile(*, user, first_name="", last_name="", email="", phone_number=""):
    """Update basic profile fields for the current user.

    This keeps all tenant and role constraints on the User model intact and
    does not allow changing security-sensitive flags (tenant, role,
    is_super_admin, etc.).
    """
    if not getattr(user, "is_authenticated", False):
        raise ValidationError({"__all__": "Authentication required."})

    User = get_user_model()

    # Super Admins are allowed to edit their own basic profile data as well,
    # but they must not gain tenant bindings here.
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    email = (email or "").strip()
    phone_number = (phone_number or "").strip()

    user.first_name = first_name
    user.last_name = last_name
    user.email = email
    user.phone_number = phone_number

    # Enforce model-level validation and business rules.
    user.full_clean()
    user.save(update_fields=["first_name", "last_name", "email", "phone_number", "updated_at"])

    return user
