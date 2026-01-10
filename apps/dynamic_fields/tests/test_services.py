from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.core.exceptions import ValidationError

from apps.tenants.models import Tenant
from apps.core.models.customer import Customer
from apps.dynamic_fields.models import FieldDefinition, FieldValue
from apps.dynamic_fields import services as df_services


class DynamicFieldsServicesTests(TestCase):
    def setUp(self):
        self.t1 = Tenant.objects.create(name="T1", slug="t1", is_active=True)
        self.t2 = Tenant.objects.create(name="T2", slug="t2", is_active=True)
        self.customer = Customer.objects.create(
            tenant=self.t1,
            customer_type=Customer.CUSTOMER_TYPE_INDIVIDUAL,
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="+255700000011",
        )

    def test_required_text_validation(self):
        d = FieldDefinition.objects.create(
            tenant=self.t1,
            entity_type=FieldDefinition.ENTITY_CUSTOMER,
            name="Customer Code",
            key="customer_code",
            data_type=FieldDefinition.TYPE_TEXT,
            is_required=True,
        )
        # Missing value should raise
        with self.assertRaises(ValidationError):
            df_services.set_field_value(definition=d, obj=self.customer, value=None, tenant=self.t1)
        # Non-empty value should pass
        fv = df_services.set_field_value(definition=d, obj=self.customer, value="ABC123", tenant=self.t1)
        self.assertIsInstance(fv, FieldValue)
        self.assertEqual(fv.text_value, "ABC123")

    def test_tenant_mismatch_rejected(self):
        d = FieldDefinition.objects.create(
            tenant=self.t1,
            entity_type=FieldDefinition.ENTITY_CUSTOMER,
            name="Segment",
            key="segment",
            data_type=FieldDefinition.TYPE_DROPDOWN,
            options=["A", "B"],
        )
        with self.assertRaises(ValidationError):
            df_services.set_field_value(definition=d, obj=self.customer, value="A", tenant=self.t2)

    def test_bulk_set_by_keys_ignores_unknown(self):
        d = FieldDefinition.objects.create(
            tenant=self.t1,
            entity_type=FieldDefinition.ENTITY_CUSTOMER,
            name="Flag",
            key="flag",
            data_type=FieldDefinition.TYPE_BOOLEAN,
        )
        res = df_services.bulk_set_by_keys(tenant=self.t1, entity_type=FieldDefinition.ENTITY_CUSTOMER, obj=self.customer, values={
            "flag": True,
            "unknown_key": "ignored",
        })
        self.assertIn("flag", res)
        self.assertEqual(res["flag"].bool_value, True)
