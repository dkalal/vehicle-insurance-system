import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.models.customer import Customer
from apps.core.services import customer_service, vehicle_service
from apps.core.services import vehicle_access_service

REQUIRED_COLUMNS = {
    'customer_type',
    'email',
    'phone',
    'vehicle_type',
    'registration_number',
    'make',
    'model',
    'year',
}


def _norm(value: Optional[str]) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _row_value(row: Dict[str, str], key: str) -> str:
    return _norm(row.get(key, ''))


def _find_existing_customer(*, tenant, customer_type: str, id_number: str,
                            company_registration_number: str, email: str) -> Optional[Customer]:
    qs = Customer.objects.filter(tenant=tenant, deleted_at__isnull=True, customer_type=customer_type)
    if customer_type == Customer.CUSTOMER_TYPE_INDIVIDUAL and id_number:
        return qs.filter(id_number=id_number).first()
    if customer_type == Customer.CUSTOMER_TYPE_COMPANY and company_registration_number:
        return qs.filter(registration_number=company_registration_number).first()
    if email:
        return qs.filter(email=email).first()
    return None


def _validate_required(row: Dict[str, str], row_num: int) -> List[str]:
    errors = []
    for col in REQUIRED_COLUMNS:
        if not _row_value(row, col):
            errors.append(f"{col} is required")
    customer_type = _row_value(row, 'customer_type').lower()
    if customer_type == Customer.CUSTOMER_TYPE_INDIVIDUAL:
        if not _row_value(row, 'first_name'):
            errors.append('first_name is required for individual customers')
        if not _row_value(row, 'last_name'):
            errors.append('last_name is required for individual customers')
    elif customer_type == Customer.CUSTOMER_TYPE_COMPANY:
        if not _row_value(row, 'company_name'):
            errors.append('company_name is required for company customers')
    elif customer_type:
        errors.append('customer_type must be individual or company')
    return errors


def import_vehicles_from_csv(*, tenant, user, file_obj) -> Dict[str, object]:
    if tenant is None or getattr(user, 'tenant_id', None) != getattr(tenant, 'id', None):
        raise ValidationError({'tenant': 'Invalid tenant context for import'})

    errors = []
    created = 0

    file_obj.seek(0)
    wrapper = io.TextIOWrapper(file_obj, encoding='utf-8-sig')
    reader = csv.DictReader(wrapper)

    if not reader.fieldnames:
        return {'created': 0, 'errors': [{'row': 0, 'errors': ['CSV header row is missing.']}]}

    normalized_headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = sorted(REQUIRED_COLUMNS - normalized_headers)
    if missing:
        return {
            'created': 0,
            'errors': [{'row': 0, 'errors': [f"Missing required columns: {', '.join(missing)}"]}],
        }

    for row_num, raw_row in enumerate(reader, start=2):
        row = {str(k).strip().lower(): _norm(v) for k, v in (raw_row or {}).items()}
        row_errors = _validate_required(row, row_num)
        if row_errors:
            errors.append({'row': row_num, 'errors': row_errors})
            continue

        customer_type = _row_value(row, 'customer_type').lower()
        vehicle_type = _row_value(row, 'vehicle_type').lower()

        try:
            vehicle_access_service.ensure_user_can_use_vehicle_type(user=user, vehicle_type=vehicle_type)
        except ValidationError as exc:
            row_errors = exc.message_dict.get('vehicle_type', [str(exc)])
            errors.append({'row': row_num, 'errors': row_errors})
            continue

        try:
            year = int(_row_value(row, 'year'))
        except (TypeError, ValueError):
            errors.append({'row': row_num, 'errors': ['year must be a valid integer']})
            continue

        seating_capacity = _row_value(row, 'seating_capacity')
        if seating_capacity:
            try:
                seating_capacity = int(seating_capacity)
            except (TypeError, ValueError):
                errors.append({'row': row_num, 'errors': ['seating_capacity must be a valid integer']})
                continue
        else:
            seating_capacity = None

        engine_capacity = _row_value(row, 'engine_capacity')
        if engine_capacity:
            try:
                engine_capacity = Decimal(engine_capacity)
            except (InvalidOperation, TypeError, ValueError):
                errors.append({'row': row_num, 'errors': ['engine_capacity must be a valid number']})
                continue
        else:
            engine_capacity = None

        with transaction.atomic():
            try:
                customer = _find_existing_customer(
                    tenant=tenant,
                    customer_type=customer_type,
                    id_number=_row_value(row, 'id_number'),
                    company_registration_number=_row_value(row, 'company_registration_number'),
                    email=_row_value(row, 'email'),
                )
                if customer is None:
                    customer = customer_service.create_customer(
                        created_by=user,
                        customer_type=customer_type,
                        email=_row_value(row, 'email'),
                        phone=_row_value(row, 'phone'),
                        first_name=_row_value(row, 'first_name'),
                        last_name=_row_value(row, 'last_name'),
                        id_number=_row_value(row, 'id_number'),
                        company_name=_row_value(row, 'company_name'),
                        registration_number=_row_value(row, 'company_registration_number'),
                        tax_id=_row_value(row, 'tax_id'),
                        address=_row_value(row, 'address'),
                        city=_row_value(row, 'city'),
                        region=_row_value(row, 'region'),
                        postal_code=_row_value(row, 'postal_code'),
                        notes=_row_value(row, 'customer_notes'),
                    )

                vehicle_service.create_vehicle(
                    created_by=user,
                    owner=customer,
                    vehicle_type=vehicle_type,
                    registration_number=_row_value(row, 'registration_number'),
                    make=_row_value(row, 'make'),
                    model=_row_value(row, 'model'),
                    year=year,
                    color=_row_value(row, 'color'),
                    chassis_number=_row_value(row, 'chassis_number'),
                    engine_number=_row_value(row, 'engine_number'),
                    seating_capacity=seating_capacity,
                    engine_capacity=engine_capacity,
                    notes=_row_value(row, 'vehicle_notes'),
                )
                created += 1
            except ValidationError as exc:
                row_errors = []
                if isinstance(exc.message_dict, dict):
                    for field, msgs in exc.message_dict.items():
                        for msg in (msgs if isinstance(msgs, (list, tuple)) else [msgs]):
                            row_errors.append(f"{field}: {msg}")
                else:
                    row_errors.append(str(exc))
                errors.append({'row': row_num, 'errors': row_errors})

    return {'created': created, 'errors': errors}
