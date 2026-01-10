from django.test import TestCase

from apps.tenants.models import Tenant
from apps.tenants.context import set_current_tenant, clear_current_tenant
from apps.core.models.customer import Customer


class TenantManagersTests(TestCase):
    def setUp(self):
        self.t1 = Tenant.objects.create(name="T1", slug="t1", is_active=True)
        self.t2 = Tenant.objects.create(name="T2", slug="t2", is_active=True)
        self.c1 = Customer.objects.create(
            tenant=self.t1,
            customer_type=Customer.CUSTOMER_TYPE_INDIVIDUAL,
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="+255700000001",
        )
        self.c2 = Customer.objects.create(
            tenant=self.t2,
            customer_type=Customer.CUSTOMER_TYPE_INDIVIDUAL,
            first_name="Jane",
            last_name="Roe",
            email="jane@example.com",
            phone="+255700000002",
        )

    def tearDown(self):
        clear_current_tenant()

    def test_manager_scopes_to_current_tenant(self):
        set_current_tenant(self.t1)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Customer.objects.first().tenant_id, self.t1.id)

        set_current_tenant(self.t2)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Customer.objects.first().tenant_id, self.t2.id)

    def test_without_tenant_returns_empty(self):
        clear_current_tenant()
        self.assertEqual(Customer.objects.count(), 0)
