from django.db import transaction
from django.utils import timezone

from apps.core.models.onboarding import TenantOnboardingState


@transaction.atomic
def get_or_create_state(*, tenant, user=None) -> TenantOnboardingState:
    state, _ = TenantOnboardingState.objects.get_or_create(
        tenant=tenant,
        defaults={
            "created_by": user,
            "updated_by": user,
        },
    )
    return state


def needs_onboarding(*, tenant) -> bool:
    state = TenantOnboardingState.objects.filter(tenant=tenant, deleted_at__isnull=True).first()
    if not state:
        return True
    return state.status != TenantOnboardingState.STATUS_COMPLETED


def should_redirect_to_onboarding_on_login(*, tenant) -> bool:
    """Return True only for brand-new tenants with no onboarding state yet.

    This is used at login time so that admins/managers are guided through
    onboarding on first access, but are not forced back into the wizard on
    every subsequent login once onboarding has been started.
    """
    state = TenantOnboardingState.objects.filter(tenant=tenant, deleted_at__isnull=True).first()
    return state is None


@transaction.atomic
def mark_welcome_shown(*, tenant, user=None) -> TenantOnboardingState:
    state = get_or_create_state(tenant=tenant, user=user)
    state.status = TenantOnboardingState.STATUS_WELCOME_SHOWN
    state.current_step = "welcome"
    state.updated_by = user
    state.save(update_fields=["status", "current_step", "updated_by", "updated_at"])
    return state


@transaction.atomic
def mark_company_setup(*, tenant, user=None) -> TenantOnboardingState:
    state = get_or_create_state(tenant=tenant, user=user)
    state.status = TenantOnboardingState.STATUS_COMPANY_SETUP
    state.current_step = "company"
    state.updated_by = user
    state.save(update_fields=["status", "current_step", "updated_by", "updated_at"])
    return state


@transaction.atomic
def update_company_context(*, tenant, user=None, name=None, contact_email=None, contact_phone=None,
                           operation_type=None, region=None, city=None) -> TenantOnboardingState:
    if name:
        tenant.name = name.strip()
    if contact_email:
        tenant.contact_email = contact_email.strip()
    if contact_phone:
        tenant.contact_phone = contact_phone.strip()
    if operation_type is not None:
        tenant.settings["operation_type"] = operation_type
    if region is not None:
        tenant.settings["default_region"] = region
    if city is not None:
        tenant.settings["default_city"] = city
    tenant.save(update_fields=["name", "contact_email", "contact_phone", "settings", "updated_at"])
    return mark_company_setup(tenant=tenant, user=user)


@transaction.atomic
def mark_vehicle_basics(*, tenant, user=None) -> TenantOnboardingState:
    state = get_or_create_state(tenant=tenant, user=user)
    state.status = TenantOnboardingState.STATUS_VEHICLE_BASICS
    state.current_step = "vehicle_basics"
    state.updated_by = user
    state.save(update_fields=["status", "current_step", "updated_by", "updated_at"])
    return state


@transaction.atomic
def mark_vehicle_owner(*, tenant, user=None, vehicle=None) -> TenantOnboardingState:
    state = get_or_create_state(tenant=tenant, user=user)
    state.status = TenantOnboardingState.STATUS_VEHICLE_OWNER
    state.current_step = "vehicle_owner"
    if vehicle:
        state.first_vehicle = vehicle
    state.updated_by = user
    state.save(update_fields=["status", "current_step", "first_vehicle", "updated_by", "updated_at"])
    return state


@transaction.atomic
def mark_vehicle_documents(*, tenant, user=None) -> TenantOnboardingState:
    state = get_or_create_state(tenant=tenant, user=user)
    state.status = TenantOnboardingState.STATUS_VEHICLE_DOCUMENTS
    state.current_step = "vehicle_documents"
    state.updated_by = user
    state.save(update_fields=["status", "current_step", "updated_by", "updated_at"])
    return state


@transaction.atomic
def mark_completed(*, tenant, user=None) -> TenantOnboardingState:
    state = get_or_create_state(tenant=tenant, user=user)
    state.status = TenantOnboardingState.STATUS_COMPLETED
    state.current_step = ""
    state.completed_at = timezone.now()
    state.updated_by = user
    state.save(update_fields=["status", "current_step", "completed_at", "updated_by", "updated_at"])
    return state
