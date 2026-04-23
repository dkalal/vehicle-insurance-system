from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.tenants.models import Tenant
from apps.core.models import SupportRequest, SupportRequestEvent

User = get_user_model()


class TenantSupportFlowTests(TestCase):
    def setUp(self):
        self.t1 = Tenant.objects.create(name="T1", slug="t1", is_active=True)
        self.u1 = User.objects.create_user(username="u1", email="u1@example.com", password="x", tenant=self.t1, role="admin")
        self.client.force_login(self.u1)
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(self.u1)

    def test_support_create_success(self):
        url = reverse("dashboard:support_create")
        resp = self.client.post(url, {
            "request_type": "policy",
            "subject": "Cannot issue policy",
            "message": "Error occurs when clicking save",
            "priority": "normal",
            "policy_reference": "POL-100",
        })
        self.assertEqual(resp.status_code, 302)
        ticket = SupportRequest.objects.get(tenant=self.t1, subject="Cannot issue policy")
        self.assertEqual(ticket.request_type, SupportRequest.REQUEST_TYPE_POLICY)
        self.assertEqual(ticket.policy_reference, "POL-100")
        self.assertTrue(
            SupportRequestEvent.objects.filter(
                tenant=self.t1,
                support_request=ticket,
                event_type=SupportRequestEvent.EVENT_CREATED,
            ).exists()
        )

    def test_support_create_csrf_enforced(self):
        # Post without CSRF token should be forbidden when checks enforced
        url = reverse("dashboard:support_create")
        resp = self.csrf_client.post(url, {
            "request_type": "general",
            "subject": "No CSRF",
            "message": "",
            "priority": "low",
        })
        self.assertIn(resp.status_code, (403, 400))

    def test_support_detail_shows_tenant_visible_timeline_only(self):
        ticket = SupportRequest.objects.create(
            tenant=self.t1,
            subject="Need help",
            message="Blocked",
            priority=SupportRequest.PRIORITY_NORMAL,
            request_type=SupportRequest.REQUEST_TYPE_GENERAL,
            created_by=self.u1,
            updated_by=self.u1,
        )
        SupportRequestEvent.objects.create(
            tenant=self.t1,
            support_request=ticket,
            event_type=SupportRequestEvent.EVENT_PUBLIC_REPLY,
            visibility=SupportRequestEvent.VISIBILITY_TENANT,
            message="Public update",
            created_by=self.u1,
            updated_by=self.u1,
        )
        SupportRequestEvent.objects.create(
            tenant=self.t1,
            support_request=ticket,
            event_type=SupportRequestEvent.EVENT_INTERNAL_NOTE,
            visibility=SupportRequestEvent.VISIBILITY_INTERNAL,
            message="Internal only",
            created_by=self.u1,
            updated_by=self.u1,
        )

        resp = self.client.get(reverse("dashboard:support_detail", args=[ticket.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Public update")
        self.assertNotContains(resp, "Internal only")

    def test_agent_only_sees_own_support_requests(self):
        agent = User.objects.create_user(
            username="agent1",
            email="agent1@example.com",
            password="x",
            tenant=self.t1,
            role="agent",
        )
        other_user = User.objects.create_user(
            username="u2",
            email="u2@example.com",
            password="x",
            tenant=self.t1,
            role="agent",
        )
        own_ticket = SupportRequest.objects.create(
            tenant=self.t1,
            subject="My ticket",
            message="Mine",
            priority=SupportRequest.PRIORITY_NORMAL,
            request_type=SupportRequest.REQUEST_TYPE_GENERAL,
            created_by=agent,
            updated_by=agent,
        )
        SupportRequest.objects.create(
            tenant=self.t1,
            subject="Other ticket",
            message="Not mine",
            priority=SupportRequest.PRIORITY_NORMAL,
            request_type=SupportRequest.REQUEST_TYPE_GENERAL,
            created_by=other_user,
            updated_by=other_user,
        )

        self.client.force_login(agent)
        resp = self.client.get(reverse("dashboard:support_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "My ticket")
        self.assertNotContains(resp, "Other ticket")

        detail = self.client.get(reverse("dashboard:support_detail", args=[own_ticket.pk]))
        self.assertEqual(detail.status_code, 200)

    def test_agent_cannot_open_another_users_support_request(self):
        agent = User.objects.create_user(
            username="agent1",
            email="agent1@example.com",
            password="x",
            tenant=self.t1,
            role="agent",
        )
        other_user = User.objects.create_user(
            username="u2",
            email="u2@example.com",
            password="x",
            tenant=self.t1,
            role="agent",
        )
        other_ticket = SupportRequest.objects.create(
            tenant=self.t1,
            subject="Other ticket",
            message="Not mine",
            priority=SupportRequest.PRIORITY_NORMAL,
            request_type=SupportRequest.REQUEST_TYPE_GENERAL,
            created_by=other_user,
            updated_by=other_user,
        )

        self.client.force_login(agent)
        resp = self.client.get(reverse("dashboard:support_detail", args=[other_ticket.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_manager_can_review_tenant_support_requests(self):
        manager = User.objects.create_user(
            username="manager1",
            email="manager1@example.com",
            password="x",
            tenant=self.t1,
            role="manager",
        )
        other_user = User.objects.create_user(
            username="u2",
            email="u2@example.com",
            password="x",
            tenant=self.t1,
            role="agent",
        )
        other_ticket = SupportRequest.objects.create(
            tenant=self.t1,
            subject="Shared tenant ticket",
            message="Needs oversight",
            priority=SupportRequest.PRIORITY_HIGH,
            request_type=SupportRequest.REQUEST_TYPE_GENERAL,
            created_by=other_user,
            updated_by=other_user,
        )

        self.client.force_login(manager)
        resp = self.client.get(reverse("dashboard:support_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Shared tenant ticket")

        detail = self.client.get(reverse("dashboard:support_detail", args=[other_ticket.pk]))
        self.assertEqual(detail.status_code, 200)
