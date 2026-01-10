from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.tenants.models import Tenant
from apps.core.models.customer import Customer
from apps.core.services.customer_service import create_customer
from apps.core.services.vehicle_service import create_vehicle
from apps.core.services.policy_service import create_policy, renew_policy
from apps.core.services.payment_service import add_payment_and_activate_policy
from django.core.exceptions import ValidationError


class ServiceLayerTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="TestCo", slug="testco", is_active=True)
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="admin1",
            email="admin1@testco.com",
            password="Strong!Pass123",
            tenant=self.tenant,
            role=User.ROLE_ADMIN,
            is_super_admin=False,
        )

    def test_create_customer_individual(self):
        c = create_customer(
            created_by=self.admin,
            customer_type=Customer.CUSTOMER_TYPE_INDIVIDUAL,
            email="john@example.com",
            phone="+255700000001",
            first_name="John",
            last_name="Doe",
        )
        self.assertEqual(c.tenant_id, self.admin.tenant_id)
        self.assertEqual(c.customer_type, Customer.CUSTOMER_TYPE_INDIVIDUAL)

    def test_create_customer_company(self):
        c = create_customer(
            created_by=self.admin,
            customer_type=Customer.CUSTOMER_TYPE_COMPANY,
            email="corp@example.com",
            phone="+255700000002",
            company_name="Corp Ltd",
        )
        self.assertEqual(c.customer_type, Customer.CUSTOMER_TYPE_COMPANY)

    def test_create_vehicle_tenant_mismatch_rejected(self):
        other_tenant = Tenant.objects.create(name="OtherCo", slug="otherco", is_active=True)
        User = get_user_model()
        other_admin = User.objects.create_user(
            username="admin2",
            email="admin2@otherco.com",
            password="Strong!Pass123",
            tenant=other_tenant,
            role=User.ROLE_ADMIN,
            is_super_admin=False,
        )
        customer = create_customer(
            created_by=other_admin,
            customer_type=Customer.CUSTOMER_TYPE_INDIVIDUAL,
            email="jane@example.com",
            phone="+255700000003",
            first_name="Jane",
            last_name="Roe",
        )
        with self.assertRaises(ValidationError):
            create_vehicle(
                created_by=self.admin,
                owner=customer,
                vehicle_type="car",
                registration_number="T123 ABC",
                make="Toyota",
                model="RAV4",
                year=2020,
            )

    def _make_customer_and_vehicle(self):
        cust = create_customer(
            created_by=self.admin,
            customer_type=Customer.CUSTOMER_TYPE_INDIVIDUAL,
            email="active@example.com",
            phone="+255700000004",
            first_name="Active",
            last_name="User",
        )
        veh = create_vehicle(
            created_by=self.admin,
            owner=cust,
            vehicle_type="car",
            registration_number="T999 XYZ",
            make="Toyota",
            model="Corolla",
            year=2021,
        )
        return cust, veh

    def test_policy_activation_after_full_payment(self):
        _, vehicle = self._make_customer_and_vehicle()
        start = date.today()
        end = start + timedelta(days=365)
        policy = create_policy(
            created_by=self.admin,
            vehicle=vehicle,
            start_date=start,
            end_date=end,
            premium_amount=Decimal("100.00"),
            coverage_amount=Decimal("10000.00"),
            policy_type="Comprehensive",
        )
        # Not active until paid fully
        self.assertNotEqual(policy.status, policy.STATUS_ACTIVE)
        # Partial payment should not activate
        add_payment_and_activate_policy(
            created_by=self.admin,
            policy=policy,
            amount=Decimal("50.00"),
            payment_method="cash",
            reference_number="P01",
        )
        policy.refresh_from_db()
        self.assertNotEqual(policy.status, policy.STATUS_ACTIVE)
        # Full payment now activates
        add_payment_and_activate_policy(
            created_by=self.admin,
            policy=policy,
            amount=Decimal("50.00"),
            payment_method="cash",
            reference_number="P02",
        )
        policy.refresh_from_db()
        self.assertEqual(policy.status, policy.STATUS_ACTIVE)

    def test_only_one_active_policy_per_vehicle(self):
        _, vehicle = self._make_customer_and_vehicle()
        start = date.today()
        end = start + timedelta(days=365)
        p1 = create_policy(
            created_by=self.admin,
            vehicle=vehicle,
            start_date=start,
            end_date=end,
            premium_amount=Decimal("100.00"),
        )
        add_payment_and_activate_policy(
            created_by=self.admin,
            policy=p1,
            amount=Decimal("100.00"),
            payment_method="cash",
            reference_number="A1",
        )
        p1.refresh_from_db()
        self.assertTrue(p1.is_active())
        # Attempt to create and activate a second overlapping policy should fail at activation
        p2 = create_policy(
            created_by=self.admin,
            vehicle=vehicle,
            start_date=start,
            end_date=end,
            premium_amount=Decimal("120.00"),
        )
        add_payment_and_activate_policy(
            created_by=self.admin,
            policy=p2,
            amount=Decimal("120.00"),
            payment_method="cash",
            reference_number="A2",
        )
        p2.refresh_from_db()
        # p2 should not be active due to existing active policy
        self.assertNotEqual(p2.status, p2.STATUS_ACTIVE)

    def test_policy_renewal(self):
        _, vehicle = self._make_customer_and_vehicle()
        start = date.today()
        end = start + timedelta(days=365)
        p1 = create_policy(
            created_by=self.admin,
            vehicle=vehicle,
            start_date=start,
            end_date=end,
            premium_amount=Decimal("100.00"),
        )
        add_payment_and_activate_policy(
            created_by=self.admin,
            policy=p1,
            amount=Decimal("100.00"),
            payment_method="cash",
            reference_number="R1",
        )
        p1.refresh_from_db()
        self.assertTrue(p1.is_active())
        # Renew starting next day after end
        p2 = renew_policy(
            created_by=self.admin,
            existing_policy=p1,
            new_start_date=end + timedelta(days=1),
            new_end_date=end + timedelta(days=366),
            new_premium_amount=Decimal("110.00"),
        )
        # Pay and activate renewal; should be allowed because no overlap of active policies
        add_payment_and_activate_policy(
            created_by=self.admin,
            policy=p2,
            amount=Decimal("110.00"),
            payment_method="cash",
            reference_number="R2",
        )
        p2.refresh_from_db()
        self.assertTrue(p2.is_active())
