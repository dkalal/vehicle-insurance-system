from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.models.customer import Customer


@transaction.atomic
def create_customer(*, created_by, customer_type, email, phone, **kwargs) -> Customer:
    """
    Create a customer (individual or company) enforcing business rules.

    Args:
        created_by: User creating this record (used for audit fields)
        customer_type: 'individual' or 'company'
        email: contact email
        phone: contact phone
        kwargs: additional fields depending on type
            - individual: first_name, last_name, id_number, date_of_birth
            - company: company_name, registration_number, tax_id
    Returns:
        Customer instance
    """
    if customer_type not in {Customer.CUSTOMER_TYPE_INDIVIDUAL, Customer.CUSTOMER_TYPE_COMPANY}:
        raise ValidationError({"customer_type": "Invalid customer type"})

    # Ensure creator is a tenant user
    creator_tenant = getattr(created_by, 'tenant', None)
    if creator_tenant is None:
        raise ValidationError({"tenant": "Creator must belong to a tenant"})

    data = {
        "customer_type": customer_type,
        "email": email,
        "phone": phone,
        "tenant": creator_tenant,
        "created_by": created_by,
        "updated_by": created_by,
    }

    if customer_type == Customer.CUSTOMER_TYPE_INDIVIDUAL:
        data.update({
            "first_name": kwargs.get("first_name", "").strip(),
            "last_name": kwargs.get("last_name", "").strip(),
            "id_number": kwargs.get("id_number", "").strip(),
            "date_of_birth": kwargs.get("date_of_birth"),
        })
        if not data["first_name"] or not data["last_name"]:
            raise ValidationError({
                "first_name": "First name required for individuals",
                "last_name": "Last name required for individuals",
            })
        if data["id_number"]:
            if Customer._base_manager.filter(
                tenant=creator_tenant,
                deleted_at__isnull=True,
                customer_type=Customer.CUSTOMER_TYPE_INDIVIDUAL,
                id_number=data["id_number"],
            ).exists():
                raise ValidationError({"id_number": "A customer with this ID number already exists in your tenant"})
    else:
        data.update({
            "company_name": kwargs.get("company_name", "").strip(),
            "registration_number": kwargs.get("registration_number", "").strip(),
            "tax_id": kwargs.get("tax_id", "").strip(),
        })
        if not data["company_name"]:
            raise ValidationError({"company_name": "Company name is required"})
        if data["registration_number"]:
            if Customer._base_manager.filter(
                tenant=creator_tenant,
                deleted_at__isnull=True,
                customer_type=Customer.CUSTOMER_TYPE_COMPANY,
                registration_number=data["registration_number"],
            ).exists():
                raise ValidationError({"registration_number": "A company with this registration number already exists in your tenant"})

    customer = Customer(**data)
    customer.full_clean()
    customer.save()
    return customer


@transaction.atomic
def update_customer(*, updated_by, customer: Customer, **kwargs) -> Customer:
    """
    Update a customer enforcing business rules and tenant boundaries.

    Args:
        updated_by: User performing the update
        customer: Customer instance to update (must belong to same tenant)
        kwargs: fields to update consistent with create rules
    Returns:
        Updated Customer instance
    """
    if customer is None:
        raise ValidationError({"customer": "Customer is required"})

    # Defense-in-depth: ensure same tenant
    if getattr(updated_by, 'tenant_id', None) != getattr(customer, 'tenant_id', None):
        raise ValidationError({"customer": "Customer must belong to your tenant"})

    for field, value in kwargs.items():
        if hasattr(customer, field):
            setattr(customer, field, value)

    customer.updated_by = updated_by

    if customer.customer_type == Customer.CUSTOMER_TYPE_INDIVIDUAL:
        if not (customer.first_name or "").strip() or not (customer.last_name or "").strip():
            raise ValidationError({
                "first_name": "First name required for individuals",
                "last_name": "Last name required for individuals",
            })
        if (customer.id_number or "").strip():
            if Customer._base_manager.filter(
                tenant=customer.tenant,
                deleted_at__isnull=True,
                customer_type=Customer.CUSTOMER_TYPE_INDIVIDUAL,
                id_number=customer.id_number.strip(),
            ).exclude(pk=customer.pk).exists():
                raise ValidationError({"id_number": "A customer with this ID number already exists in your tenant"})
    else:
        if not (customer.company_name or "").strip():
            raise ValidationError({"company_name": "Company name is required"})
        if (customer.registration_number or "").strip():
            if Customer._base_manager.filter(
                tenant=customer.tenant,
                deleted_at__isnull=True,
                customer_type=Customer.CUSTOMER_TYPE_COMPANY,
                registration_number=customer.registration_number.strip(),
            ).exclude(pk=customer.pk).exists():
                raise ValidationError({"registration_number": "A company with this registration number already exists in your tenant"})

    customer.full_clean()
    customer.save()
    return customer


@transaction.atomic
def soft_delete_customer(*, deleted_by, customer: Customer) -> Customer:
    """
    Soft delete a customer (no destructive delete). Records audit via BaseModel.
    """
    if customer is None:
        raise ValidationError({"customer": "Customer is required"})
    if getattr(deleted_by, 'tenant_id', None) != getattr(customer, 'tenant_id', None):
        raise ValidationError({"customer": "Customer must belong to your tenant"})
    # Track who performed deletion
    customer.updated_by = deleted_by
    customer.save(update_fields=['updated_by'])
    customer.soft_delete()
    return customer
