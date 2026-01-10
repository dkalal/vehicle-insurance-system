from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.tenants.models import Tenant
from apps.super_admin.models import PlatformConfig


User = get_user_model()


class MaintenanceModeMiddlewareTests(TestCase):
    def setUp(self):
        self.t1 = Tenant.objects.create(name="T1", slug="t1", is_active=True)
        self.super_admin = User.objects.create_user(
            username="sa", email="sa@example.com", password="x", is_super_admin=True
        )
        self.u1 = User.objects.create_user(
            username="u1", email="u1@example.com", password="x", tenant=self.t1, role="admin"
        )
        # Ensure singleton exists
        self.cfg = PlatformConfig.get_solo()

    def test_maintenance_blocks_tenant_allows_super_admin(self):
        self.cfg.maintenance_mode = True
        self.cfg.save()

        # Tenant user blocked with 503
        self.client.force_login(self.u1)
        resp = self.client.get(reverse("dashboard:home"))
        self.assertEqual(resp.status_code, 503)

        # Super admin allowed
        self.client.force_login(self.super_admin)
        resp2 = self.client.get(reverse("super_admin:home"))
        self.assertEqual(resp2.status_code, 200)
