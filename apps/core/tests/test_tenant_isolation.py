from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.tenants.models import Tenant
from apps.core.models import Customer, Vehicle

User = get_user_model()


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.t1 = Tenant.objects.create(name="T1", slug="t1", is_active=True)
        self.t2 = Tenant.objects.create(name="T2", slug="t2", is_active=True)
        self.u1 = User.objects.create_user(username="u1", password="x", tenant=self.t1, role="admin")

        # Create cross-tenant records
        self.c2 = Customer.objects.create(
            tenant=self.t2,
            customer_type="individual",
            first_name="Alice",
            last_name="Other",
            email="alice@example.com",
        )
        self.v2 = Vehicle.objects.create(
            tenant=self.t2,
            owner=self.c2,
            vehicle_type="car",
            registration_number="T2-XYZ-123",
        )

    def test_list_views_do_not_expose_other_tenant_records(self):
        self.client.force_login(self.u1)
        # Vehicles list should not include T2 registration number
        resp_v = self.client.get(reverse("dashboard:vehicles_list"))
        self.assertEqual(resp_v.status_code, 200)
        self.assertNotContains(resp_v, "T2-XYZ-123")

        # Customers list should not include T2 customer name
        resp_c = self.client.get(reverse("dashboard:customers_list"))
        self.assertEqual(resp_c.status_code, 200)
        self.assertNotContains(resp_c, "Alice Other")

    def test_update_views_block_cross_tenant_access(self):
        self.client.force_login(self.u1)
        # Attempt editing T2 vehicle/customer must 404
        resp_v = self.client.get(reverse("dashboard:vehicles_update", args=[self.v2.pk]))
        self.assertEqual(resp_v.status_code, 404)

        resp_c = self.client.get(reverse("dashboard:customers_update", args=[self.c2.pk]))
        self.assertEqual(resp_c.status_code, 404)
