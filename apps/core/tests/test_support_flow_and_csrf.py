from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.tenants.models import Tenant
from apps.core.models import SupportRequest

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
            "subject": "Cannot issue policy",
            "message": "Error occurs when clicking save",
            "priority": "normal",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(SupportRequest.objects.filter(tenant=self.t1, subject="Cannot issue policy").exists())

    def test_support_create_csrf_enforced(self):
        # Post without CSRF token should be forbidden when checks enforced
        url = reverse("dashboard:support_create")
        resp = self.csrf_client.post(url, {
            "subject": "No CSRF",
            "message": "",
            "priority": "low",
        })
        self.assertIn(resp.status_code, (403, 400))
