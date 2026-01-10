"""
Comprehensive testing utilities and configuration for Vehicle Insurance System.
Provides factories, fixtures, and testing helpers for world-class test coverage.
"""

import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.db import transaction
from decimal import Decimal
from datetime import date, timedelta

from apps.tenants.models import Tenant
from apps.core.models import Customer, Vehicle, Policy, Payment

User = get_user_model()


class TenantFactory(DjangoModelFactory):
    """Factory for creating test tenants."""
    
    class Meta:
        model = Tenant
    
    name = factory.Sequence(lambda n: f"Test Insurance Company {n}")
    slug = factory.LazyAttribute(lambda obj: obj.name.lower().replace(' ', '-'))
    contact_email = factory.LazyAttribute(lambda obj: f"contact@{obj.slug}.com")
    contact_phone = "+255123456789"
    is_active = True


class UserFactory(DjangoModelFactory):
    """Factory for creating test users."""
    
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    tenant = factory.SubFactory(TenantFactory)
    role = User.ROLE_AGENT


class SuperAdminUserFactory(UserFactory):
    """Factory for creating super admin users."""
    
    tenant = None
    role = None
    is_super_admin = True


class CustomerFactory(DjangoModelFactory):
    """Factory for creating test customers."""
    
    class Meta:
        model = Customer
    
    tenant = factory.SubFactory(TenantFactory)
    customer_type = 'individual'
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    email = factory.LazyAttribute(lambda obj: f"{obj.first_name.lower()}.{obj.last_name.lower()}@example.com")
    phone_number = factory.Faker('phone_number')
    address = factory.Faker('address')
    date_of_birth = factory.Faker('date_of_birth', minimum_age=18, maximum_age=80)


class VehicleFactory(DjangoModelFactory):
    """Factory for creating test vehicles."""
    
    class Meta:
        model = Vehicle
    
    tenant = factory.SelfAttribute('owner.tenant')
    owner = factory.SubFactory(CustomerFactory)
    vehicle_type = 'car'
    make = factory.Faker('company')
    model = factory.Faker('word')
    year = factory.Faker('random_int', min=2000, max=2024)
    registration_number = factory.Sequence(lambda n: f"T{n:03d}ABC")
    vin = factory.Faker('bothify', text='?#?#?#?#?#?#?#?#?')
    color = factory.Faker('color_name')


class PolicyFactory(DjangoModelFactory):
    """Factory for creating test policies."""
    
    class Meta:
        model = Policy
    
    tenant = factory.SelfAttribute('vehicle.tenant')
    vehicle = factory.SubFactory(VehicleFactory)
    policy_number = factory.Sequence(lambda n: f"POL-2024-TEST-{n:05d}")
    start_date = factory.LazyFunction(date.today)
    end_date = factory.LazyAttribute(lambda obj: obj.start_date + timedelta(days=365))
    premium_amount = factory.Faker('pydecimal', left_digits=6, right_digits=2, positive=True)
    coverage_amount = factory.LazyAttribute(lambda obj: obj.premium_amount * 10)
    status = Policy.STATUS_PENDING_PAYMENT
    policy_type = 'Comprehensive'


class PaymentFactory(DjangoModelFactory):
    """Factory for creating test payments."""
    
    class Meta:
        model = Payment
    
    tenant = factory.SelfAttribute('policy.tenant')
    policy = factory.SubFactory(PolicyFactory)
    amount = factory.LazyAttribute(lambda obj: obj.policy.premium_amount)
    payment_date = factory.LazyFunction(date.today)
    payment_method = 'bank_transfer'
    reference_number = factory.Sequence(lambda n: f"PAY{n:08d}")
    is_verified = True


class BaseTestCase(TestCase):
    """
    Base test case with common setup and utilities.
    """
    
    def setUp(self):
        """Set up test data."""
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant, role=User.ROLE_ADMIN)
        self.super_admin = SuperAdminUserFactory()
        
    def create_customer(self, **kwargs):
        """Create a customer for the test tenant."""
        kwargs.setdefault('tenant', self.tenant)
        return CustomerFactory(**kwargs)
    
    def create_vehicle(self, **kwargs):
        """Create a vehicle for the test tenant."""
        if 'owner' not in kwargs:
            kwargs['owner'] = self.create_customer()
        return VehicleFactory(**kwargs)
    
    def create_policy(self, **kwargs):
        """Create a policy for the test tenant."""
        if 'vehicle' not in kwargs:
            kwargs['vehicle'] = self.create_vehicle()
        return PolicyFactory(**kwargs)
    
    def create_payment(self, **kwargs):
        """Create a payment for the test tenant."""
        if 'policy' not in kwargs:
            kwargs['policy'] = self.create_policy()
        return PaymentFactory(**kwargs)
    
    def login_as_user(self, user=None):
        """Login as a specific user."""
        user = user or self.user
        self.client.force_login(user)
        return user
    
    def login_as_super_admin(self):
        """Login as super admin."""
        self.client.force_login(self.super_admin)
        return self.super_admin


class TenantIsolationTestCase(BaseTestCase):
    """
    Test case specifically for testing tenant isolation.
    """
    
    def setUp(self):
        super().setUp()
        # Create second tenant with data
        self.tenant2 = TenantFactory()
        self.user2 = UserFactory(tenant=self.tenant2, role=User.ROLE_ADMIN)
        self.customer2 = CustomerFactory(tenant=self.tenant2)
        self.vehicle2 = VehicleFactory(tenant=self.tenant2, owner=self.customer2)
        self.policy2 = PolicyFactory(tenant=self.tenant2, vehicle=self.vehicle2)
    
    def assert_tenant_isolation(self, queryset, expected_tenant):
        """Assert that queryset only contains records for expected tenant."""
        for obj in queryset:
            self.assertEqual(obj.tenant, expected_tenant, 
                           f"Found {obj} belonging to {obj.tenant}, expected {expected_tenant}")


def create_test_tenant_with_data():
    """Create a tenant with complete test data."""
    tenant = TenantFactory()
    admin_user = UserFactory(tenant=tenant, role=User.ROLE_ADMIN)
    manager_user = UserFactory(tenant=tenant, role=User.ROLE_MANAGER)
    agent_user = UserFactory(tenant=tenant, role=User.ROLE_AGENT)
    
    customers = CustomerFactory.create_batch(5, tenant=tenant)
    vehicles = []
    policies = []
    
    for customer in customers:
        vehicle = VehicleFactory(tenant=tenant, owner=customer)
        vehicles.append(vehicle)
        
        policy = PolicyFactory(tenant=tenant, vehicle=vehicle, status=Policy.STATUS_ACTIVE)
        policies.append(policy)
        
        # Create payment for policy
        PaymentFactory(tenant=tenant, policy=policy, amount=policy.premium_amount)
    
    return {
        'tenant': tenant,
        'users': {
            'admin': admin_user,
            'manager': manager_user,
            'agent': agent_user,
        },
        'customers': customers,
        'vehicles': vehicles,
        'policies': policies,
    }