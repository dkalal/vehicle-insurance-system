from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Customer, Policy, Vehicle, LATRARecord, PermitType, VehiclePermit
from apps.tenants.models import Tenant


User = get_user_model()


class ReportsViewsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Fleet Ops Ltd",
            slug="fleet-ops",
            contact_email="ops@example.com",
            is_active=True,
        )
        self.admin = User.objects.create_user(
            username="tenant-admin",
            email="admin@fleetops.test",
            password="Pass!12345",
            tenant=self.tenant,
            role=User.ROLE_ADMIN,
        )
        self.other_tenant = Tenant.objects.create(
            name="Other Fleet Ltd",
            slug="other-fleet",
            contact_email="other@example.com",
            is_active=True,
        )

        self.company = Customer.objects.create(
            tenant=self.tenant,
            customer_type=Customer.CUSTOMER_TYPE_COMPANY,
            company_name="Trans East",
            registration_number="COMP-001",
            email="fleet@transeast.test",
            phone="+255700000001",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.individual = Customer.objects.create(
            tenant=self.tenant,
            customer_type=Customer.CUSTOMER_TYPE_INDIVIDUAL,
            first_name="Asha",
            last_name="Mtei",
            id_number="ID-001",
            email="asha@demo.test",
            phone="+255700000002",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.other_customer = Customer.objects.create(
            tenant=self.other_tenant,
            customer_type=Customer.CUSTOMER_TYPE_COMPANY,
            company_name="Hidden Fleet",
            registration_number="COMP-999",
            email="hidden@example.com",
            phone="+255700000099",
        )

        self.company_vehicle = Vehicle.objects.create(
            tenant=self.tenant,
            owner=self.company,
            vehicle_type=Vehicle.VEHICLE_TYPE_CAR,
            registration_number="T 111 AAA",
            make="Toyota",
            model="Coaster",
            year=2024,
            chassis_number="CH-111",
            engine_number="EN-111",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.company_risk_vehicle = Vehicle.objects.create(
            tenant=self.tenant,
            owner=self.company,
            vehicle_type=Vehicle.VEHICLE_TYPE_CAR,
            registration_number="T 112 AAA",
            make="Nissan",
            model="Civilian",
            year=2023,
            chassis_number="CH-112",
            engine_number="EN-112",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.individual_vehicle = Vehicle.objects.create(
            tenant=self.tenant,
            owner=self.individual,
            vehicle_type=Vehicle.VEHICLE_TYPE_MOTORCYCLE,
            registration_number="MC 200 BBB",
            make="Yamaha",
            model="XTZ",
            year=2022,
            chassis_number="CH-200",
            engine_number="EN-200",
            created_by=self.admin,
            updated_by=self.admin,
        )
        Vehicle.objects.create(
            tenant=self.other_tenant,
            owner=self.other_customer,
            vehicle_type=Vehicle.VEHICLE_TYPE_CAR,
            registration_number="T 999 ZZZ",
            make="Scania",
            model="Bus",
            year=2021,
        )

        today = timezone.localdate()
        Policy.objects.create(
            tenant=self.tenant,
            vehicle=self.company_vehicle,
            policy_number="POL-TEST-0001",
            start_date=today,
            end_date=today + timedelta(days=120),
            premium_amount="100000.00",
            status=Policy.STATUS_ACTIVE,
            created_by=self.admin,
            updated_by=self.admin,
        )
        Policy.objects.create(
            tenant=self.tenant,
            vehicle=self.company_risk_vehicle,
            policy_number="POL-TEST-0002",
            start_date=today,
            end_date=today + timedelta(days=10),
            premium_amount="100000.00",
            status=Policy.STATUS_ACTIVE,
            created_by=self.admin,
            updated_by=self.admin,
        )

        permit_type = PermitType.objects.create(
            tenant=self.tenant,
            name="Route Permit",
        )
        LATRARecord.objects.create(
            tenant=self.tenant,
            vehicle=self.company_vehicle,
            latra_number="LATRA-001",
            license_type="PSV",
            route="City Centre",
            start_date=today,
            end_date=today + timedelta(days=60),
            status=LATRARecord.STATUS_ACTIVE,
            created_by=self.admin,
            updated_by=self.admin,
        )
        VehiclePermit.objects.create(
            tenant=self.tenant,
            vehicle=self.company_vehicle,
            permit_type=permit_type,
            reference_number="PERMIT-001",
            start_date=today,
            end_date=today + timedelta(days=45),
            status=VehiclePermit.STATUS_ACTIVE,
            created_by=self.admin,
            updated_by=self.admin,
        )

    def test_reports_home_renders_hub_metrics(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("dashboard:reports_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reports Hub")
        self.assertContains(response, "Customer Portfolio Visibility")
        self.assertContains(response, "Open customer portfolios")
        self.assertContains(response, "Policies Expiring Soon")

    def test_customer_portfolios_report_is_vehicle_first_and_tenant_scoped(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("dashboard:reports_customers"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trans East")
        self.assertContains(response, "Asha Mtei")
        self.assertContains(response, "2")
        self.assertNotContains(response, "Hidden Fleet")

    def test_customer_portfolio_detail_supports_vehicle_register_export(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("dashboard:reports_customer_detail", args=[self.company.pk]) + "?export=csv"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode("utf-8")
        self.assertIn("Registration Number", content)
        self.assertIn("T 111 AAA", content)
        self.assertIn("T 112 AAA", content)
