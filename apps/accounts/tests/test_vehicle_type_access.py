from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.tenants.models import Tenant
from apps.core.models.vehicle import Vehicle
from apps.accounts.services import vehicle_type_access_service
from apps.core.services import vehicle_access_service
from apps.core.models.vehicle import Vehicle as VehicleModel
from apps.core.models.customer import Customer


class VehicleTypeAccessTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="ScopeCo", slug="scopeco", is_active=True)
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="admin1",
            email="admin1@scopeco.com",
            password="Strong!Pass123",
            tenant=self.tenant,
            role=User.ROLE_ADMIN,
            is_super_admin=False,
        )
        self.agent = User.objects.create_user(
            username="agent1",
            email="agent1@scopeco.com",
            password="Strong!Pass123",
            tenant=self.tenant,
            role=User.ROLE_AGENT,
            is_super_admin=False,
        )
        # One customer to own vehicles
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            customer_type=Customer.CUSTOMER_TYPE_INDIVIDUAL,
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="+255700000200",
        )

    def test_admin_sees_all_vehicle_types_by_default(self):
        allowed = self.admin.get_allowed_vehicle_types()
        expected = {t for (t, _) in Vehicle.VEHICLE_TYPE_CHOICES}
        self.assertEqual(allowed, expected)

    def test_agent_restricted_to_configured_vehicle_types(self):
        vehicle_type_access_service.set_user_vehicle_types(
            tenant=self.tenant,
            user=self.agent,
            vehicle_types=[Vehicle.VEHICLE_TYPE_CAR],
            updated_by=self.admin,
        )
        allowed = self.agent.get_allowed_vehicle_types()
        self.assertEqual(allowed, {Vehicle.VEHICLE_TYPE_CAR})

    def test_filter_vehicle_queryset_for_user_respects_assignments(self):
        # Create one car and one motorcycle in this tenant
        car = VehicleModel.objects.create(
            tenant=self.tenant,
            owner=self.customer,
            vehicle_type=Vehicle.VEHICLE_TYPE_CAR,
            registration_number="T111 CAR",
            make="Toyota",
            model="Corolla",
            year=2020,
        )
        moto = VehicleModel.objects.create(
            tenant=self.tenant,
            owner=self.customer,
            vehicle_type=Vehicle.VEHICLE_TYPE_MOTORCYCLE,
            registration_number="T222 MOTO",
            make="Honda",
            model="CBR",
            year=2020,
        )

        # Scope agent to cars only
        vehicle_type_access_service.set_user_vehicle_types(
            tenant=self.tenant,
            user=self.agent,
            vehicle_types=[Vehicle.VEHICLE_TYPE_CAR],
            updated_by=self.admin,
        )

        qs = VehicleModel.objects.all()
        filtered = vehicle_access_service.filter_vehicle_queryset_for_user(user=self.agent, queryset=qs)
        self.assertIn(car, list(filtered))
        self.assertNotIn(moto, list(filtered))
