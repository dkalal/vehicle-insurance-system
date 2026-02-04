from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.tenants.models import Tenant
from apps.core.models.customer import Customer
from apps.core.models.vehicle import Vehicle
from apps.core.services import vehicle_import_service
from apps.accounts.services import vehicle_type_access_service


class VehicleImportServiceTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="ImportCo", slug="importco", is_active=True)
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="importadmin",
            email="importadmin@example.com",
            password="Strong!Pass123",
            tenant=self.tenant,
            role=User.ROLE_ADMIN,
            is_super_admin=False,
        )
        self.agent = User.objects.create_user(
            username="importagent",
            email="importagent@example.com",
            password="Strong!Pass123",
            tenant=self.tenant,
            role=User.ROLE_AGENT,
            is_super_admin=False,
        )

    def _make_file(self, name: str, content: str) -> SimpleUploadedFile:
        return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")

    def test_happy_path_creates_customer_and_vehicle(self):
        csv_content = (
            "customer_type,email,phone,vehicle_type,registration_number,make,model,year,first_name,last_name\n"
            "individual,john@example.com,+255700000100,car,T123 ABC,Toyota,Corolla,2020,John,Doe\n"
        )
        f = self._make_file("vehicles.csv", csv_content)

        result = vehicle_import_service.import_vehicles_from_csv(
            tenant=self.tenant,
            user=self.agent,
            file_obj=f,
        )

        self.assertEqual(result.get("created"), 1)
        self.assertEqual(result.get("errors"), [])
        self.assertEqual(Customer.objects.filter(tenant=self.tenant).count(), 1)
        self.assertEqual(Vehicle.objects.filter(tenant=self.tenant).count(), 1)
        v = Vehicle.objects.get(tenant=self.tenant)
        self.assertEqual(v.registration_number, "T123 ABC")

    def test_invalid_tenant_context_raises(self):
        other_tenant = Tenant.objects.create(name="Other", slug="other", is_active=True)
        csv_content = (
            "customer_type,email,phone,vehicle_type,registration_number,make,model,year,first_name,last_name\n"
            "individual,jane@example.com,+255700000101,car,T999 XYZ,Toyota,Corolla,2021,Jane,Roe\n"
        )
        f = self._make_file("vehicles.csv", csv_content)

        with self.assertRaises(ValidationError):
            vehicle_import_service.import_vehicles_from_csv(
                tenant=other_tenant,
                user=self.admin,
                file_obj=f,
            )

    def test_missing_required_header_returns_header_error(self):
        # Omit the 'make' column
        csv_content = (
            "customer_type,email,phone,vehicle_type,registration_number,model,year,first_name,last_name\n"
            "individual,john@example.com,+255700000102,car,T123 ABC,Corolla,2020,John,Doe\n"
        )
        f = self._make_file("bad.csv", csv_content)

        result = vehicle_import_service.import_vehicles_from_csv(
            tenant=self.tenant,
            user=self.agent,
            file_obj=f,
        )

        self.assertEqual(result.get("created"), 0)
        errors = result.get("errors") or []
        self.assertTrue(errors)
        self.assertEqual(errors[0].get("row"), 0)
        self.assertIn("Missing required columns", " ".join(errors[0].get("errors") or []))

    def test_disallowed_vehicle_type_row_is_rejected(self):
        # Restrict agent to cars only
        vehicle_type_access_service.set_user_vehicle_types(
            tenant=self.tenant,
            user=self.agent,
            vehicle_types=["car"],
            updated_by=self.admin,
        )
        csv_content = (
            "customer_type,email,phone,vehicle_type,registration_number,make,model,year,first_name,last_name\n"
            "individual,john@example.com,+255700000103,motorcycle,T123 MOTO,Honda,CBR,2020,John,Doe\n"
        )
        f = self._make_file("vehicles.csv", csv_content)

        result = vehicle_import_service.import_vehicles_from_csv(
            tenant=self.tenant,
            user=self.admin,
            file_obj=f,
        )

        self.assertEqual(result.get("created"), 0)
        errors = result.get("errors") or []
        self.assertEqual(len(errors), 1)
        combined = " ".join(errors[0].get("errors") or [])
        self.assertIn("vehicle type", combined.lower())

    def test_invalid_year_gives_row_error(self):
        csv_content = (
            "customer_type,email,phone,vehicle_type,registration_number,make,model,year,first_name,last_name\n"
            "individual,john@example.com,+255700000104,car,T123 BAD,Toyota,Corolla,notayear,John,Doe\n"
        )
        f = self._make_file("vehicles.csv", csv_content)

        result = vehicle_import_service.import_vehicles_from_csv(
            tenant=self.tenant,
            user=self.admin,
            file_obj=f,
        )

        self.assertEqual(result.get("created"), 0)
        errors = result.get("errors") or []
        self.assertEqual(len(errors), 1)
        self.assertIn("year must be a valid integer", " ".join(errors[0].get("errors") or []))
