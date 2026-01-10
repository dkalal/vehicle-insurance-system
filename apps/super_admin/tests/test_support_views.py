from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.tenants.models import Tenant
from apps.core.models import SupportRequest

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
        resp2 = self.client.post(edit, {"status": "in_progress", "priority": "high", "assigned_to": "", "resolved_at": ""})
        # Update view redirects on success
        self.assertEqual(resp2.status_code, 302)
