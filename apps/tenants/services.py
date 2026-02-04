from django.db import transaction
from django.utils.text import slugify
from typing import Optional, Dict

from .models import Tenant


@transaction.atomic
def create_tenant(*, name: str, slug: Optional[str] = None, domain: Optional[str] = None,
                  contact_email: str, contact_phone: str = "", settings: Optional[Dict] = None,
                  is_active: bool = True) -> Tenant:
    t = Tenant(
        name=name.strip(),
        slug=(slug.strip() if slug else None),
        domain=(domain.strip() if domain else None),
        contact_email=contact_email.strip(),
        contact_phone=(contact_phone or "").strip(),
        settings=settings or {},
        is_active=is_active,
    )
    # Model will auto-generate slug if missing
    t.full_clean()
    t.save()
    return t


@transaction.atomic
def update_tenant(*, tenant: Tenant, name: str, slug: Optional[str], domain: Optional[str],
                  contact_email: str, contact_phone: str = "", settings: Optional[Dict] = None,
                  is_active: bool = True) -> Tenant:
    tenant.name = name.strip()
    tenant.slug = (slug.strip() if slug else tenant.slug)
    tenant.domain = (domain.strip() if domain else None)
    tenant.contact_email = contact_email.strip()
    tenant.contact_phone = (contact_phone or "").strip()
    tenant.settings = settings or {}
    tenant.is_active = is_active
    tenant.full_clean()
    tenant.save()
    return tenant


def activate_tenant(tenant: Tenant) -> Tenant:
    tenant.activate()
    return tenant


def deactivate_tenant(tenant: Tenant) -> Tenant:
    tenant.deactivate()
    return tenant


def soft_delete_tenant(tenant: Tenant) -> Tenant:
    tenant.soft_delete()
    return tenant


@transaction.atomic
def update_tenant_settings_for_admin(*,
                                     tenant: Tenant,
                                     name: str,
                                     contact_email: str,
                                     contact_phone: str = "",
                                     operation_type: str | None = None,
                                     region: str | None = None,
                                     city: str | None = None,
                                     expiry_reminder_days: int | None = None) -> Tenant:
    """Update a tenant's organization settings from the tenant admin dashboard.

    This intentionally exposes only a safe subset of fields for tenant admins
    and leaves platform-level concerns (slug, domain, activation) to the
    Super Admin flows.
    """

    tenant.name = (name or "").strip()
    tenant.contact_email = (contact_email or "").strip()
    tenant.contact_phone = (contact_phone or "").strip()

    # Update structured settings while preserving any other keys
    settings = dict(tenant.settings or {})
    if operation_type is not None:
        settings["operation_type"] = operation_type
    if region is not None:
        settings["default_region"] = region
    if city is not None:
        settings["default_city"] = city
    if expiry_reminder_days is not None:
        try:
            settings["expiry_reminder_days"] = int(expiry_reminder_days)
        except (TypeError, ValueError):
            settings["expiry_reminder_days"] = None

    tenant.settings = settings
    tenant.full_clean()
    tenant.save(update_fields=["name", "contact_email", "contact_phone", "settings", "updated_at"])
    return tenant
