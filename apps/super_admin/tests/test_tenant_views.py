from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.tenants.models import Tenant


User = get_user_model()


class TenantManagementViewTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user(
            username="sa",
            email="sa@example.com",
            password="x",
            is_super_admin=True,
        )

    def test_super_admin_can_create_tenant(self):
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("super_admin:tenant_create"),
            {
                "name": "Vehicle Operations Demo",
                "slug": "vehicle-operations-demo",
                "domain": "",
                "contact_email": "ops@example.com",
                "contact_phone": "",
                "is_active": "on",
                "settings": "{}",
            },
        )

        self.assertRedirects(response, reverse("super_admin:tenants"))
        self.assertTrue(
            Tenant.objects.filter(slug="vehicle-operations-demo").exists()
        )

    def test_super_admin_can_create_tenant_with_blank_slug_and_settings(self):
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("super_admin:tenant_create"),
            {
                "name": "Vehicle Registry Board",
                "slug": "",
                "domain": "",
                "contact_email": "registry@example.com",
                "contact_phone": "",
                "is_active": "on",
                "settings": "",
            },
        )

        self.assertRedirects(response, reverse("super_admin:tenants"))
        tenant = Tenant.objects.get(slug="vehicle-registry-board")
        self.assertEqual(tenant.settings, {})

    def test_super_admin_can_create_tenant_with_first_admin(self):
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("super_admin:tenant_create"),
            {
                "name": "Logistics Vehicle Authority",
                "slug": "logistics-vehicle-authority",
                "domain": "",
                "contact_email": "logistics@example.com",
                "contact_phone": "",
                "is_active": "on",
                "settings": "{}",
                "admin_username": "logistics_admin",
                "admin_email": "admin@logistics.example.com",
                "admin_password": "VehicleDemo123!",
            },
        )

        self.assertRedirects(response, reverse("super_admin:tenants"))
        tenant = Tenant.objects.get(slug="logistics-vehicle-authority")
        admin = User.objects.get(username="logistics_admin")
        self.assertEqual(admin.tenant, tenant)
        self.assertEqual(admin.role, User.ROLE_ADMIN)
        self.assertFalse(admin.is_super_admin)
        self.assertTrue(admin.check_password("VehicleDemo123!"))

    def test_first_admin_username_must_be_unique(self):
        User.objects.create_user(
            username="existing_admin",
            email="existing@example.com",
            password="x",
            is_super_admin=True,
        )
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("super_admin:tenant_create"),
            {
                "name": "Duplicate Admin Demo",
                "slug": "duplicate-admin-demo",
                "domain": "",
                "contact_email": "duplicate@example.com",
                "contact_phone": "",
                "is_active": "on",
                "settings": "{}",
                "admin_username": "existing_admin",
                "admin_email": "new@example.com",
                "admin_password": "VehicleDemo123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Tenant.objects.filter(slug="duplicate-admin-demo").exists())
        self.assertContains(response, "A user with this username already exists")

    def test_super_admin_can_add_admin_to_existing_tenant(self):
        tenant = Tenant.objects.create(
            name="No Admin Tenant",
            slug="no-admin-tenant",
            contact_email="tenant@example.com",
        )
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("super_admin:tenant_admin", args=[tenant.pk]),
            {
                "username": "no_admin_tenant_admin",
                "email": "admin@tenant.example.com",
                "password": "VehicleDemo123!",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("super_admin:tenants"))
        admin = User.objects.get(username="no_admin_tenant_admin")
        self.assertEqual(admin.tenant, tenant)
        self.assertEqual(admin.role, User.ROLE_ADMIN)
        self.assertTrue(admin.check_password("VehicleDemo123!"))

    def test_super_admin_can_update_tenant(self):
        tenant = Tenant.objects.create(
            name="Old Name",
            slug="old-name",
            contact_email="old@example.com",
        )
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("super_admin:tenant_update", args=[tenant.pk]),
            {
                "name": "Vehicle Fleet Authority",
                "slug": "vehicle-fleet-authority",
                "domain": "",
                "contact_email": "fleet@example.com",
                "contact_phone": "",
                "is_active": "on",
                "settings": "{}",
            },
        )

        self.assertRedirects(response, reverse("super_admin:tenants"))
        tenant.refresh_from_db()
        self.assertEqual(tenant.name, "Vehicle Fleet Authority")
