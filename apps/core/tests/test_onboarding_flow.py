from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.tenants.models import Tenant
from apps.core.models import TenantOnboardingState, Vehicle
from apps.core.services import onboarding_service


User = get_user_model()


class OnboardingServiceTests(TestCase):
    def setUp(self):
        self.tenant1 = Tenant.objects.create(name="Tenant 1", slug="tenant-1", is_active=True, contact_email="t1@example.com")
        self.tenant2 = Tenant.objects.create(name="Tenant 2", slug="tenant-2", is_active=True, contact_email="t2@example.com")

    def test_needs_onboarding_for_new_tenant(self):
        # No state yet -> onboarding required
        self.assertTrue(onboarding_service.needs_onboarding(tenant=self.tenant1))

    def test_state_is_per_tenant(self):
        # Complete onboarding for tenant1 only
        onboarding_service.mark_completed(tenant=self.tenant1, user=None)
        state1 = TenantOnboardingState.objects.get(tenant=self.tenant1)
        self.assertEqual(state1.status, TenantOnboardingState.STATUS_COMPLETED)

        # Tenant2 should still need onboarding and have independent state
        self.assertTrue(onboarding_service.needs_onboarding(tenant=self.tenant2))
        state2 = onboarding_service.get_or_create_state(tenant=self.tenant2, user=None)
        self.assertNotEqual(state2.tenant_id, state1.tenant_id)
        self.assertNotEqual(state2.pk, state1.pk)


class OnboardingViewsFlowTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Flow Tenant", slug="flow-tenant", is_active=True, contact_email="flow@example.com")
        self.admin = User.objects.create_user(
            username="flowadmin",
            email="flowadmin@example.com",
            password="Strong!Pass123",
            tenant=self.tenant,
            role=User.ROLE_ADMIN,
            is_super_admin=False,
        )
        self.client.force_login(self.admin)

    def test_full_onboarding_flow_marks_completed_and_creates_vehicle(self):
        # Start at welcome
        resp = self.client.get(reverse("dashboard:onboarding_welcome"))
        self.assertEqual(resp.status_code, 200)

        # Welcome -> POST advances to company step and marks welcome_shown
        resp = self.client.post(reverse("dashboard:onboarding_welcome"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("dashboard:onboarding_company"))
        state = TenantOnboardingState.objects.get(tenant=self.tenant)
        self.assertEqual(state.status, TenantOnboardingState.STATUS_WELCOME_SHOWN)

        # Company step -> POST updates tenant and moves to vehicle basics
        company_data = {
            "name": "Flow Tenant Updated",
            "contact_email": "updated@example.com",
            "contact_phone": "+255700000000",
            "operation_type": "insurance",
            "region": "Dar",
            "city": "Dar es Salaam",
        }
        resp = self.client.post(reverse("dashboard:onboarding_company"), data=company_data)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("dashboard:onboarding_vehicle_basics"))
        self.tenant.refresh_from_db()
        state.refresh_from_db()
        self.assertEqual(state.status, TenantOnboardingState.STATUS_COMPANY_SETUP)
        self.assertEqual(self.tenant.name, "Flow Tenant Updated")
        self.assertEqual(self.tenant.contact_email, "updated@example.com")

        # Vehicle basics -> POST stores basics and advances to owner step
        vehicle_data = {
            "registration_number": "T123ABC",
            "vehicle_type": "car",
            "make": "Toyota",
            "model": "Corolla",
            "year": 2020,
            "color": "White",
        }
        resp = self.client.post(reverse("dashboard:onboarding_vehicle_basics"), data=vehicle_data)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("dashboard:onboarding_owner"))
        state.refresh_from_db()
        self.assertEqual(state.status, TenantOnboardingState.STATUS_VEHICLE_BASICS)

        # Owner step -> POST creates owner + vehicle and moves to documents
        owner_data = {
            "customer_type": User.ROLE_ADMIN and "individual" or "individual",
            "first_name": "Alice",
            "last_name": "Owner",
            "company_name": "",
            "email": "alice.owner@example.com",
            "phone": "+255711111111",
        }
        resp = self.client.post(reverse("dashboard:onboarding_owner"), data=owner_data)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("dashboard:onboarding_documents"))
        state.refresh_from_db()
        self.assertEqual(state.status, TenantOnboardingState.STATUS_VEHICLE_OWNER)
        state.refresh_from_db()
        self.assertIsNotNone(state.first_vehicle)
        self.assertEqual(Vehicle.objects.filter(tenant=self.tenant).count(), 1)

        # Documents step -> POST completes onboarding
        resp = self.client.post(reverse("dashboard:onboarding_documents"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("dashboard:onboarding_success"))
        state.refresh_from_db()
        self.assertEqual(state.status, TenantOnboardingState.STATUS_COMPLETED)
        self.assertIsNotNone(state.completed_at)
        self.assertFalse(onboarding_service.needs_onboarding(tenant=self.tenant))

        # Once completed, visiting welcome should bounce to dashboard home
        resp = self.client.get(reverse("dashboard:onboarding_welcome"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("dashboard:home"))


class OnboardingLoginRedirectTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Login Tenant", slug="login-tenant", is_active=True, contact_email="login@example.com")
        self.login_url = reverse("accounts:login")
        self.admin = User.objects.create_user(
            username="admintenant",
            email="admintenant@example.com",
            password="Strong!Pass123",
            tenant=self.tenant,
            role=User.ROLE_ADMIN,
            is_super_admin=False,
        )
        self.agent = User.objects.create_user(
            username="agenttenant",
            email="agenttenant@example.com",
            password="Strong!Pass123",
            tenant=self.tenant,
            role=User.ROLE_AGENT,
            is_super_admin=False,
        )

    def test_admin_redirects_to_onboarding_when_needed(self):
        resp = self.client.post(
            self.login_url,
            {"username": "admintenant", "password": "Strong!Pass123"},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("dashboard:onboarding_welcome"))

    def test_admin_redirects_to_home_after_completion(self):
        # Mark onboarding completed first
        onboarding_service.mark_completed(tenant=self.tenant, user=None)
        resp = self.client.post(
            self.login_url,
            {"username": "admintenant", "password": "Strong!Pass123"},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("dashboard:home"))

    def test_agent_not_forced_into_onboarding(self):
        resp = self.client.post(
            self.login_url,
            {"username": "agenttenant", "password": "Strong!Pass123"},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        # Agents skip first-run onboarding redirect and go straight to dashboard
        self.assertEqual(resp.url, reverse("dashboard:home"))
