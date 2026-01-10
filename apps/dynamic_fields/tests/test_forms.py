from django.test import TestCase

from apps.dynamic_fields.forms import FieldDefinitionForm
from apps.dynamic_fields.models import FieldDefinition


class FieldDefinitionFormTests(TestCase):
    def _base_payload(self):
        return {
            "entity_type": FieldDefinition.ENTITY_VEHICLE,
            "name": "Doors",
            "key": "doors",
            "data_type": FieldDefinition.TYPE_DROPDOWN,
            "is_required": True,
            "is_active": True,
            "order": 1,
        }

    def test_accepts_unquoted_bracket_list(self):
        data = self._base_payload()
        data["options"] = "[single door, double doors, triple doors]"
        form = FieldDefinitionForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["options"], [
            "single door", "double doors", "triple doors"
        ])

    def test_accepts_comma_separated(self):
        data = self._base_payload()
        data["options"] = "red, green, blue"
        form = FieldDefinitionForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["options"], ["red", "green", "blue"])

    def test_accepts_newline_separated(self):
        data = self._base_payload()
        data["options"] = "gold\nsilver\nbronze"
        form = FieldDefinitionForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["options"], ["gold", "silver", "bronze"]) 
