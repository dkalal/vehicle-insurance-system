from collections import defaultdict
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from apps.core.models import Customer, Policy, Vehicle, LATRARecord, VehiclePermit
from apps.core.services import VehicleComplianceService
from apps.core.services import policy_status_service


def get_risk_window_days(*, tenant):
    try:
        return int(tenant.get_setting("expiry_reminder_days", 30))
    except Exception:
        return 30


def _customer_display_name(customer):
    if customer.customer_type == Customer.CUSTOMER_TYPE_COMPANY:
        return customer.company_name or "Unnamed company"
    return " ".join(part for part in [customer.first_name, customer.last_name] if part).strip() or "Unnamed customer"


def _build_vehicle_status_row(*, vehicle, risk_window_days):
    compliance = VehicleComplianceService.compute_compliance_status(
        vehicle=vehicle,
        risk_window_days=risk_window_days,
    )
    snapshot = VehicleComplianceService.get_compliance_snapshot(vehicle=vehicle)
    return {
        "vehicle": vehicle,
        "compliance": compliance,
        "snapshot": snapshot,
    }


def build_reports_home_context(*, tenant):
    policy_status_service.reconcile_policies(tenant=tenant)

    risk_window_days = get_risk_window_days(tenant=tenant)
    today = timezone.localdate()
    risk_cutoff = today + timedelta(days=risk_window_days)

    compliance = VehicleComplianceService.get_tenant_compliance_summary(
        tenant=tenant,
        risk_window_days=risk_window_days,
    )

    customers_qs = Customer.all_objects.filter(tenant=tenant, deleted_at__isnull=True)
    vehicles_qs = Vehicle.objects.filter(tenant=tenant, deleted_at__isnull=True)
    active_policies_qs = Policy.objects.filter(
        tenant=tenant,
        deleted_at__isnull=True,
        status=Policy.STATUS_ACTIVE,
    )

    return {
        "risk_window_days": risk_window_days,
        "compliance": compliance,
        "report_metrics": {
            "customers": customers_qs.count(),
            "companies": customers_qs.filter(customer_type=Customer.CUSTOMER_TYPE_COMPANY).count(),
            "individuals": customers_qs.filter(customer_type=Customer.CUSTOMER_TYPE_INDIVIDUAL).count(),
            "vehicles": vehicles_qs.count(),
            "active_policies": active_policies_qs.count(),
            "pending_payment_policies": Policy.objects.filter(
                tenant=tenant,
                deleted_at__isnull=True,
                status=Policy.STATUS_PENDING_PAYMENT,
            ).count(),
            "expiring_policies": active_policies_qs.filter(
                end_date__gt=today,
                end_date__lte=risk_cutoff,
            ).count(),
            "expiring_latra": LATRARecord.objects.filter(
                tenant=tenant,
                deleted_at__isnull=True,
                status=LATRARecord.STATUS_ACTIVE,
                end_date__gt=today,
                end_date__lte=risk_cutoff,
            ).count(),
            "expiring_permits": VehiclePermit.objects.filter(
                tenant=tenant,
                deleted_at__isnull=True,
                status=VehiclePermit.STATUS_ACTIVE,
                end_date__gt=today,
                end_date__lte=risk_cutoff,
            ).count(),
        },
        "expiring_policies": (
            active_policies_qs.select_related("vehicle", "vehicle__owner")
            .filter(end_date__gt=today, end_date__lte=risk_cutoff)
            .order_by("end_date")[:5]
        ),
    }


def build_customer_portfolios_context(*, tenant, customer_type="", query=""):
    policy_status_service.reconcile_policies(tenant=tenant)

    customer_type = (customer_type or "").strip()
    query = (query or "").strip()
    risk_window_days = get_risk_window_days(tenant=tenant)

    customers_qs = Customer.all_objects.filter(
        tenant=tenant,
        deleted_at__isnull=True,
    )
    if customer_type in {
        Customer.CUSTOMER_TYPE_COMPANY,
        Customer.CUSTOMER_TYPE_INDIVIDUAL,
    }:
        customers_qs = customers_qs.filter(customer_type=customer_type)
    if query:
        customers_qs = customers_qs.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(company_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(registration_number__icontains=query)
        )

    customers = list(customers_qs.order_by("customer_type", "company_name", "first_name", "last_name"))
    customer_ids = [customer.id for customer in customers]

    vehicles = list(
        Vehicle.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
            owner_id__in=customer_ids,
        )
        .select_related("owner")
        .order_by("owner_id", "registration_number")
    )

    vehicles_by_customer = defaultdict(list)
    for vehicle in vehicles:
        vehicles_by_customer[vehicle.owner_id].append(vehicle)

    rows = []
    total_vehicle_count = 0
    total_compliant = 0
    total_at_risk = 0
    total_non_compliant = 0

    for customer in customers:
        customer_vehicles = vehicles_by_customer.get(customer.id, [])
        compliant = 0
        at_risk = 0
        non_compliant = 0
        active_policies = 0
        active_latra = 0
        active_permits = 0

        for vehicle in customer_vehicles:
            result = VehicleComplianceService.compute_compliance_status(
                vehicle=vehicle,
                risk_window_days=risk_window_days,
            )
            if result["status"] == VehicleComplianceService.STATUS_COMPLIANT:
                compliant += 1
            elif result["status"] == VehicleComplianceService.STATUS_AT_RISK:
                at_risk += 1
            else:
                non_compliant += 1

            snapshot = VehicleComplianceService.get_compliance_snapshot(vehicle=vehicle)
            if snapshot["active_insurance"]:
                active_policies += 1
            if snapshot["active_latra"]:
                active_latra += 1
            if snapshot["active_permits"]:
                active_permits += 1

        total_vehicle_count += len(customer_vehicles)
        total_compliant += compliant
        total_at_risk += at_risk
        total_non_compliant += non_compliant

        rows.append(
            {
                "customer": customer,
                "display_name": _customer_display_name(customer),
                "total_vehicles": len(customer_vehicles),
                "compliant": compliant,
                "at_risk": at_risk,
                "non_compliant": non_compliant,
                "active_policies": active_policies,
                "vehicles_with_latra": active_latra,
                "vehicles_with_permits": active_permits,
            }
        )

    rows.sort(
        key=lambda row: (
            -row["non_compliant"],
            -row["at_risk"],
            -row["total_vehicles"],
            row["display_name"].lower(),
        )
    )

    return {
        "risk_window_days": risk_window_days,
        "rows": rows,
        "filters": {
            "customer_type": customer_type,
            "q": query,
        },
        "summary": {
            "customers": len(rows),
            "vehicles": total_vehicle_count,
            "compliant": total_compliant,
            "at_risk": total_at_risk,
            "non_compliant": total_non_compliant,
        },
    }


def build_customer_portfolio_detail_context(*, tenant, customer_id):
    policy_status_service.reconcile_policies(tenant=tenant)

    customer = Customer.all_objects.filter(
        tenant=tenant,
        deleted_at__isnull=True,
        pk=customer_id,
    ).first()
    if customer is None:
        raise ValidationError({"customer": "Customer not found for this tenant"})

    risk_window_days = get_risk_window_days(tenant=tenant)
    vehicles = list(
        Vehicle.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
            owner=customer,
        )
        .select_related("owner")
        .order_by("registration_number")
    )

    vehicle_rows = []
    compliant = 0
    at_risk = 0
    non_compliant = 0
    active_policies = 0
    active_latra = 0
    active_permits = 0

    for vehicle in vehicles:
        row = _build_vehicle_status_row(vehicle=vehicle, risk_window_days=risk_window_days)
        vehicle_rows.append(row)

        if row["compliance"]["status"] == VehicleComplianceService.STATUS_COMPLIANT:
            compliant += 1
        elif row["compliance"]["status"] == VehicleComplianceService.STATUS_AT_RISK:
            at_risk += 1
        else:
            non_compliant += 1

        if row["snapshot"]["active_insurance"]:
            active_policies += 1
        if row["snapshot"]["active_latra"]:
            active_latra += 1
        if row["snapshot"]["active_permits"]:
            active_permits += 1

    return {
        "customer": customer,
        "display_name": _customer_display_name(customer),
        "risk_window_days": risk_window_days,
        "vehicle_rows": vehicle_rows,
        "summary": {
            "vehicles": len(vehicle_rows),
            "compliant": compliant,
            "at_risk": at_risk,
            "non_compliant": non_compliant,
            "active_policies": active_policies,
            "vehicles_with_latra": active_latra,
            "vehicles_with_permits": active_permits,
        },
    }
