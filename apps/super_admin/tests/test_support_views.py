from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.tenants.models import Tenant
from apps.core.models import SupportRequest, SupportRequestEvent

User = get_user_model()


class SupportViewsPermissionTests(TestCase):
    def setUp(self):
        self.t1 = Tenant.objects.create(name="T1", slug="t1", is_active=True)
        self.sa = User.objects.create_user(username="sa", password="x", is_super_admin=True)
        self.u1 = User.objects.create_user(username="u1", password="x", tenant=self.t1, role="admin")
        self.ticket = SupportRequest.objects.create(
            tenant=self.t1,
            subject="Help",
            message="Something",
            request_type=SupportRequest.REQUEST_TYPE_GENERAL,
            created_by=self.u1,
            updated_by=self.u1,
        )

    def test_tenant_user_cannot_access_super_admin_support(self):
        self.client.force_login(self.u1)
        url = reverse("super_admin:support_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_super_admin_can_access_and_update(self):
        self.client.force_login(self.sa)
        url = reverse("super_admin:support_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        edit = reverse("super_admin:support_update", args=[self.ticket.pk])
        resp2 = self.client.post(edit, {
            "status": "resolved",
            "priority": "high",
            "assigned_to": str(self.sa.pk),
            "tenant_message": "We have completed the fix.",
            "internal_note": "Verified on platform side.",
            "resolution_summary": "Resolved after platform review.",
        })
        # Update view redirects on success
        self.assertEqual(resp2.status_code, 302)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, SupportRequest.STATUS_RESOLVED)
        self.assertEqual(self.ticket.assigned_to, self.sa)
        self.assertTrue(
            SupportRequestEvent.objects.filter(
                support_request=self.ticket,
                event_type=SupportRequestEvent.EVENT_RESOLVED,
            ).exists()
        )
