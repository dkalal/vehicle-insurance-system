from typing import Any, Dict, Optional
from decimal import Decimal
from datetime import date

from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from .models import FieldDefinition, FieldValue


TYPE_MAP = {
    FieldDefinition.TYPE_TEXT: "text_value",
    FieldDefinition.TYPE_NUMBER: "number_value",
    FieldDefinition.TYPE_DATE: "date_value",
    FieldDefinition.TYPE_BOOLEAN: "bool_value",
    FieldDefinition.TYPE_DROPDOWN: "option_value",
}


def _coerce_value(defn: FieldDefinition, value: Any) -> Dict[str, Any]:
    """
    Coerce incoming value to the appropriate typed column payload.
    Returns a dict {column_name: coerced_value}.
    """
    if defn.data_type == FieldDefinition.TYPE_TEXT:
        if value is None:
            return {"text_value": ""}
        return {"text_value": str(value)}

    if defn.data_type == FieldDefinition.TYPE_NUMBER:
        if value is None:
            return {"number_value": None}
        try:
            return {"number_value": Decimal(str(value))}
        except Exception as e:
            raise ValidationError({"value": f"Invalid number: {value}"}) from e

    if defn.data_type == FieldDefinition.TYPE_DATE:
        if value is None:
            return {"date_value": None}
        if isinstance(value, date):
            return {"date_value": value}
        raise ValidationError({"value": f"Invalid date: {value}"})

    if defn.data_type == FieldDefinition.TYPE_BOOLEAN:
        if value in (True, False, None):
            return {"bool_value": value}
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "1", "yes", "y"):  # convenience
                return {"bool_value": True}
            if normalized in ("false", "0", "no", "n"):
                return {"bool_value": False}
        raise ValidationError({"value": f"Invalid boolean: {value}"})

    if defn.data_type == FieldDefinition.TYPE_DROPDOWN:
        if value is None:
            return {"option_value": ""}
        option = str(value)
        if defn.options and option not in defn.options:
            raise ValidationError({"value": "Invalid option."})
        return {"option_value": option}

    raise ValidationError({"value": f"Unsupported type: {defn.data_type}"})


@transaction.atomic
def set_field_value(*, definition: FieldDefinition, obj, value: Any, tenant=None) -> FieldValue:
    """
    Create or update a FieldValue for the given object under the provided definition.
    Enforces tenant alignment and typed value rules.
    """
    if definition is None:
        raise ValidationError({"definition": "Definition is required"})

    if tenant is None:
        # Inherit tenant from definition to avoid ambiguity
        tenant = definition.tenant

    # Tenant alignment checks
    if tenant is None:
        raise ValidationError({"tenant": "Tenant is required"})
    if definition.tenant_id != tenant.id:
        raise ValidationError({"tenant": "Tenant mismatch with field definition."})

    # Determine content type + object id
    ct = ContentType.objects.get_for_model(obj.__class__)
    object_id = getattr(obj, "pk", None)
    if not object_id:
        raise ValidationError({"object": "Object must be saved before assigning field values."})

    payload = _coerce_value(definition, value)

    fv, _created = FieldValue.objects.get_or_create(
        tenant=tenant,
        definition=definition,
        content_type=ct,
        object_id=object_id,
        defaults=payload,
    )

    # Update existing
    for col in ("text_value", "number_value", "date_value", "bool_value", "option_value"):
        setattr(fv, col, payload.get(col, None) if col in payload else getattr(fv, col))

    fv.full_clean()
    fv.save()
    return fv


def get_field_value(*, definition: FieldDefinition, obj) -> Optional[Any]:
    """
    Retrieve the Python value for a given definition-object pair.
    Returns None if no value exists.
    """
    ct = ContentType.objects.get_for_model(obj.__class__)
    try:
        fv = FieldValue.objects.get(definition=definition, content_type=ct, object_id=obj.pk)
    except FieldValue.DoesNotExist:
        return None

    if definition.data_type == FieldDefinition.TYPE_TEXT:
        return fv.text_value
    if definition.data_type == FieldDefinition.TYPE_NUMBER:
        return fv.number_value
    if definition.data_type == FieldDefinition.TYPE_DATE:
        return fv.date_value
    if definition.data_type == FieldDefinition.TYPE_BOOLEAN:
        return fv.bool_value
    if definition.data_type == FieldDefinition.TYPE_DROPDOWN:
        return fv.option_value
    return None


@transaction.atomic
def bulk_set_by_keys(*, tenant, entity_type: str, obj, values: Dict[str, Any]) -> Dict[str, FieldValue]:
    """
    Convenience: set multiple dynamic fields by key for a given entity type and object.
    - Looks up definitions in the same tenant and entity_type.
    - Applies set_field_value for each key present in 'values'.
    Returns a mapping {key: FieldValue} for the updated/created rows.
    """
    if not values:
        return {}

    defs = FieldDefinition.objects.filter(tenant=tenant, entity_type=entity_type, key__in=list(values.keys()))
    def_by_key = {d.key: d for d in defs}

    result: Dict[str, FieldValue] = {}
    for key, raw_value in values.items():
        defn = def_by_key.get(key)
        if not defn:
            # Ignore unknown keys silently for robustness; alternatively raise ValidationError
            continue
        fv = set_field_value(definition=defn, obj=obj, value=raw_value, tenant=tenant)
        result[key] = fv
    return result
