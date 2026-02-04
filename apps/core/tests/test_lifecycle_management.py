"""
Tests for unified lifecycle management of Policies and Permits.

Validates:
- Immutability after activation
- State transitions
- Cancellation rules
- Audit requirements
- Vehicle constraints
"""

import pytest
from datetime import date, timedelta
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone

from apps.core.models.policy import Policy
from apps.core.models.vehicle_record import VehiclePermit, PermitType
from apps.core.services import lifecycle_service, policy_service, permit_service


@pytest.mark.django_db
class TestPolicyLifecycle:
    """Test Policy lifecycle management."""
    
    def test_policy_starts_as_pending_payment(self, tenant, user, vehicle):
        """New policies start in pending_payment state."""
        policy = policy_service.create_policy(
            created_by=user,
            vehicle=vehicle,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            premium_amount=1000
        )
        assert policy.status == Policy.STATUS_PENDING_PAYMENT
        assert policy.activated_at is None
    
    def test_cannot_activate_unpaid_policy(self, tenant, user, vehicle):
        """Policy requires full payment before activation."""
        policy = policy_service.create_policy(
            created_by=user,
            vehicle=vehicle,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            premium_amount=1000
        )
        
        with pytest.raises(ValidationError, match="fully paid"):
            lifecycle_service.activate_entity(policy.id, user, Policy)
    
    def test_policy_activation_sets_timestamp(self, tenant, admin_user, vehicle, payment):
        """Activation sets activated_at timestamp."""
        policy = payment.policy
        
        activated = lifecycle_service.activate_entity(policy.id, admin_user, Policy)
        
        assert activated.status == Policy.STATUS_ACTIVE
        assert activated.activated_at is not None
        assert activated.is_immutable()
    
    def test_cannot_activate_already_active_policy(self, tenant, admin_user, active_policy):
        """Cannot activate an already active policy."""
        with pytest.raises(ValidationError, match="already active"):
            lifecycle_service.activate_entity(active_policy.id, admin_user, Policy)
    
    def test_vehicle_cannot_have_multiple_active_policies(self, tenant, admin_user, vehicle, active_policy):
        """Vehicle can only have one active policy at a time."""
        new_policy = policy_service.create_policy(
            created_by=admin_user,
            vehicle=vehicle,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            premium_amount=1000
        )
        
        # Make it paid
        from apps.core.models.payment import Payment
        Payment.objects.create(
            tenant=tenant,
            policy=new_policy,
            amount=1000,
            is_verified=True,
            created_by=admin_user,
            updated_by=admin_user
        )
        
        with pytest.raises(ValidationError, match="already has an active policy"):
            lifecycle_service.activate_entity(new_policy.id, admin_user, Policy)
    
    def test_policy_cancellation_requires_reason(self, tenant, admin_user, active_policy):
        """Cancellation requires a reason."""
        with pytest.raises(ValidationError, match="reason is required"):
            lifecycle_service.cancel_entity(
                active_policy.id,
                admin_user,
                reason="",
                note="",
                model_class=Policy
            )
    
    def test_policy_cancellation_records_audit_data(self, tenant, admin_user, active_policy):
        """Cancellation records all audit data."""
        cancelled = lifecycle_service.cancel_entity(
            active_policy.id,
            admin_user,
            reason=Policy.CANCELLATION_REASON_CUSTOMER_REQUEST,
            note="Customer requested cancellation",
            model_class=Policy
        )
        
        assert cancelled.status == Policy.STATUS_CANCELLED
        assert cancelled.cancelled_at is not None
        assert cancelled.cancelled_by == admin_user
        assert cancelled.cancellation_reason == Policy.CANCELLATION_REASON_CUSTOMER_REQUEST
        assert cancelled.cancellation_note == "Customer requested cancellation"
    
    def test_cannot_cancel_already_cancelled_policy(self, tenant, admin_user, active_policy):
        """Cannot cancel an already cancelled policy."""
        lifecycle_service.cancel_entity(
            active_policy.id,
            admin_user,
            reason=Policy.CANCELLATION_REASON_CUSTOMER_REQUEST,
            note="",
            model_class=Policy
        )
        
        active_policy.refresh_from_db()
        
        with pytest.raises(ValidationError, match="already cancelled"):
            lifecycle_service.cancel_entity(
                active_policy.id,
                admin_user,
                reason=Policy.CANCELLATION_REASON_OTHER,
                note="",
                model_class=Policy
            )
    
    def test_super_admin_cannot_cancel_policy(self, super_admin, active_policy):
        """Super Admin cannot modify business data."""
        with pytest.raises(PermissionDenied, match="Super Admin"):
            lifecycle_service.cancel_entity(
                active_policy.id,
                super_admin,
                reason=Policy.CANCELLATION_REASON_CUSTOMER_REQUEST,
                note="",
                model_class=Policy
            )
    
    def test_agent_cannot_cancel_policy(self, tenant, agent_user, active_policy):
        """Only Admin/Manager can cancel policies."""
        with pytest.raises(PermissionDenied, match="Admin or Manager"):
            lifecycle_service.cancel_entity(
                active_policy.id,
                agent_user,
                reason=Policy.CANCELLATION_REASON_CUSTOMER_REQUEST,
                note="",
                model_class=Policy
            )


@pytest.mark.django_db
class TestPermitLifecycle:
    """Test Permit lifecycle management."""
    
    def test_permit_starts_as_draft(self, tenant, user, vehicle, permit_type):
        """New permits start in draft state."""
        permit = permit_service.create_vehicle_permit(
            created_by=user,
            vehicle=vehicle,
            permit_type=permit_type,
            reference_number="PERMIT-001",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365)
        )
        
        assert permit.status == VehiclePermit.STATUS_DRAFT
        assert permit.activated_at is None
    
    def test_permit_activation(self, tenant, admin_user, vehicle, permit_type):
        """Permit can be activated."""
        permit = permit_service.create_vehicle_permit(
            created_by=admin_user,
            vehicle=vehicle,
            permit_type=permit_type,
            reference_number="PERMIT-001",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365)
        )
        
        activated = lifecycle_service.activate_entity(permit.id, admin_user, VehiclePermit)
        
        assert activated.status == VehiclePermit.STATUS_ACTIVE
        assert activated.activated_at is not None
        assert activated.is_immutable()
    
    def test_vehicle_cannot_have_multiple_active_permits_same_type(
        self, tenant, admin_user, vehicle, permit_type
    ):
        """Vehicle cannot have multiple active permits of same type."""
        # Create and activate first permit
        permit1 = permit_service.create_vehicle_permit(
            created_by=admin_user,
            vehicle=vehicle,
            permit_type=permit_type,
            reference_number="PERMIT-001",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365)
        )
        lifecycle_service.activate_entity(permit1.id, admin_user, VehiclePermit)
        
        # Try to create and activate second permit of same type
        permit2 = permit_service.create_vehicle_permit(
            created_by=admin_user,
            vehicle=vehicle,
            permit_type=permit_type,
            reference_number="PERMIT-002",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365)
        )
        
        with pytest.raises(ValidationError, match="already has an active"):
            lifecycle_service.activate_entity(permit2.id, admin_user, VehiclePermit)
    
    def test_permit_cancellation(self, tenant, admin_user, active_permit):
        """Permit can be cancelled with reason."""
        cancelled = lifecycle_service.cancel_entity(
            active_permit.id,
            admin_user,
            reason=VehiclePermit.CANCELLATION_REASON_VEHICLE_SOLD,
            note="Vehicle was sold",
            model_class=VehiclePermit
        )
        
        assert cancelled.status == VehiclePermit.STATUS_CANCELLED
        assert cancelled.cancelled_at is not None
        assert cancelled.cancelled_by == admin_user
        assert cancelled.cancellation_reason == VehiclePermit.CANCELLATION_REASON_VEHICLE_SOLD


@pytest.mark.django_db
class TestLifecycleTimeAwareness:
    """Test time-aware lifecycle logic."""
    
    def test_get_active_window_for_active_policy(self, active_policy):
        """Active policy returns open-ended window."""
        start, end = lifecycle_service.get_active_window(active_policy)
        
        assert start is not None
        assert end is None  # Still active
    
    def test_get_active_window_for_cancelled_policy(self, tenant, admin_user, active_policy):
        """Cancelled policy returns closed window."""
        cancelled = lifecycle_service.cancel_entity(
            active_policy.id,
            admin_user,
            reason=Policy.CANCELLATION_REASON_CUSTOMER_REQUEST,
            note="",
            model_class=Policy
        )
        
        start, end = lifecycle_service.get_active_window(cancelled)
        
        assert start is not None
        assert end is not None
        assert end == cancelled.cancelled_at
    
    def test_is_active_at_checks_historical_window(self, tenant, admin_user, active_policy):
        """is_active_at respects historical active window."""
        # Policy is active today
        assert lifecycle_service.is_active_at(active_policy, date.today())
        
        # Cancel it
        cancelled = lifecycle_service.cancel_entity(
            active_policy.id,
            admin_user,
            reason=Policy.CANCELLATION_REASON_CUSTOMER_REQUEST,
            note="",
            model_class=Policy
        )
        
        # Still was active today (before cancellation)
        assert lifecycle_service.is_active_at(cancelled, date.today())
        
        # Won't be active tomorrow
        assert not lifecycle_service.is_active_at(cancelled, date.today() + timedelta(days=1))


# Fixtures
@pytest.fixture
def tenant(db):
    from apps.tenants.models import Tenant
    return Tenant.objects.create(
        name="Test Insurance Co",
        slug="test-insurance",
        contact_email="test@example.com"
    )


@pytest.fixture
def user(tenant):
    from apps.accounts.models import User
    return User.objects.create_user(
        username="testuser",
        email="user@test.com",
        password="testpass123",
        tenant=tenant,
        role=User.ROLE_AGENT
    )


@pytest.fixture
def admin_user(tenant):
    from apps.accounts.models import User
    return User.objects.create_user(
        username="admin",
        email="admin@test.com",
        password="testpass123",
        tenant=tenant,
        role=User.ROLE_ADMIN
    )


@pytest.fixture
def agent_user(tenant):
    from apps.accounts.models import User
    return User.objects.create_user(
        username="agent",
        email="agent@test.com",
        password="testpass123",
        tenant=tenant,
        role=User.ROLE_AGENT
    )


@pytest.fixture
def super_admin(db):
    from apps.accounts.models import User
    return User.objects.create_user(
        username="superadmin",
        email="super@test.com",
        password="testpass123",
        is_super_admin=True
    )


@pytest.fixture
def vehicle(tenant, user):
    from apps.core.models.vehicle import Vehicle
    return Vehicle.objects.create(
        tenant=tenant,
        registration_number="ABC123",
        chassis_number="CHASSIS123",
        vehicle_type=Vehicle.VEHICLE_TYPE_PRIVATE,
        created_by=user,
        updated_by=user
    )


@pytest.fixture
def payment(tenant, user, vehicle):
    """Create a paid policy."""
    from apps.core.models.payment import Payment
    
    policy = policy_service.create_policy(
        created_by=user,
        vehicle=vehicle,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        premium_amount=1000
    )
    
    payment = Payment.objects.create(
        tenant=tenant,
        policy=policy,
        amount=1000,
        is_verified=True,
        created_by=user,
        updated_by=user
    )
    
    return payment


@pytest.fixture
def active_policy(tenant, admin_user, vehicle):
    """Create an active policy."""
    from apps.core.models.payment import Payment
    
    policy = policy_service.create_policy(
        created_by=admin_user,
        vehicle=vehicle,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        premium_amount=1000
    )
    
    Payment.objects.create(
        tenant=tenant,
        policy=policy,
        amount=1000,
        is_verified=True,
        created_by=admin_user,
        updated_by=admin_user
    )
    
    lifecycle_service.activate_entity(policy.id, admin_user, Policy)
    policy.refresh_from_db()
    return policy


@pytest.fixture
def permit_type(tenant, admin_user):
    """Create a permit type."""
    return PermitType.objects.create(
        tenant=tenant,
        name="Road License",
        is_active=True
    )


@pytest.fixture
def active_permit(tenant, admin_user, vehicle, permit_type):
    """Create an active permit."""
    permit = permit_service.create_vehicle_permit(
        created_by=admin_user,
        vehicle=vehicle,
        permit_type=permit_type,
        reference_number="PERMIT-001",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365)
    )
    
    lifecycle_service.activate_entity(permit.id, admin_user, VehiclePermit)
    permit.refresh_from_db()
    return permit
