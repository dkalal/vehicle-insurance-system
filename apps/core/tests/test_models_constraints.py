from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from apps.tenants.models import Tenant
from apps.core.models.customer import Customer


class CustomerModelConstraintsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme Insure", slug="acme-insure", is_active=True)
        User = get_user_model()
        self.user = User.objects.create_user(
            username="admin1",
            email="admin1@acme.com",
            password="Pass!12345",
            tenant=self.tenant,
            role=User.ROLE_ADMIN,
            is_super_admin=False,
        )

    def test_individual_requires_names(self):
        c = Customer(
            tenant=self.tenant,
            customer_type=Customer.CUSTOMER_TYPE_INDIVIDUAL,
            email="john@acme.com",
            phone="+255712345678",
            created_by=self.user,
            updated_by=self.user,
        )
        with self.assertRaises(ValidationError):
            c.full_clean()

        c.first_name = "John"
        c.last_name = "Doe"
        c.full_clean()  # should not raise now

    def test_company_requires_company_name(self):
        c = Customer(
            tenant=self.tenant,
            customer_type=Customer.CUSTOMER_TYPE_COMPANY,
            email="corp@acme.com",
            phone="+255712345679",
            created_by=self.user,
            updated_by=self.user,
        )
        with self.assertRaises(ValidationError):
            c.full_clean()

        c.company_name = "ACME Logistics"
        c.full_clean()  # should not raise now
