from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction


@transaction.atomic
def create_staff_user(*, created_by, username, email, first_name="", last_name="", phone_number="", role="agent", is_active=True):
    """Create a tenant-scoped staff user for the creator's company.

    Only tenant admins are allowed to create staff. The new user will:
    - Belong to the same tenant as the creator
    - Never be a super admin
    - Have a generated random password (to be delivered out-of-band)
    """
    User = get_user_model()

    if not getattr(created_by, "tenant_id", None):
        raise ValidationError({"__all__": "Creator must belong to a tenant."})
    if getattr(created_by, "is_super_admin", False):
        raise ValidationError({"__all__": "Super Admin cannot create tenant staff from dashboard."})
    if getattr(created_by, "role", None) != User.ROLE_ADMIN:
        raise ValidationError({"__all__": "Only tenant admins can create staff users."})

    username = (username or "").strip()
    email = (email or "").strip()
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    phone_number = (phone_number or "").strip()

    if not username:
        raise ValidationError({"username": "Username is required."})

    # Basic role validation; detailed rules live on the User model
    valid_roles = {User.ROLE_ADMIN, User.ROLE_MANAGER, User.ROLE_AGENT}
    if role not in valid_roles:
        raise ValidationError({"role": "Invalid role for tenant staff user."})

    temp_password = User.objects.make_random_password()

    user = User.objects.create_user(
        username=username,
        email=email,
        password=temp_password,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        tenant=created_by.tenant,
        role=role,
        is_super_admin=False,
        is_active=bool(is_active),
    )
    # Attach the raw password in-memory so the caller can show it once to the admin.
    # This attribute is NOT persisted to the database.
    user._raw_password = temp_password
    return user
