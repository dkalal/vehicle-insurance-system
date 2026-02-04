# Lifecycle Management Quick Reference

## Service Functions

```python
from apps.core.services import policy_service, permit_service, lifecycle_service
from apps.core.models.policy import Policy
from apps.core.models.vehicle_record import VehiclePermit

# Activate Policy (requires full payment)
policy = lifecycle_service.activate_entity(policy_id, actor, Policy)

# Cancel Policy
policy = policy_service.cancel_policy(
    policy_id=policy.id,
    actor=request.user,
    reason=Policy.CANCELLATION_REASON_CUSTOMER_REQUEST,
    note="Optional details"
)

# Activate Permit
permit = lifecycle_service.activate_entity(permit_id, actor, VehiclePermit)

# Cancel Permit
permit = permit_service.cancel_permit(
    permit_id=permit.id,
    actor=request.user,
    reason=VehiclePermit.CANCELLATION_REASON_VEHICLE_SOLD,
    note="Optional details"
)

# Check if immutable
if entity.is_immutable():
    # Cannot edit

# Get active window
start, end = lifecycle_service.get_active_window(entity)

# Check if active at date
was_active = lifecycle_service.is_active_at(entity, check_date)
```

## Cancellation Reasons

### Policy
- `CANCELLATION_REASON_CUSTOMER_REQUEST`
- `CANCELLATION_REASON_NON_PAYMENT`
- `CANCELLATION_REASON_VEHICLE_SOLD`
- `CANCELLATION_REASON_DUPLICATE`
- `CANCELLATION_REASON_ERROR`
- `CANCELLATION_REASON_OTHER`

### Permit
- `CANCELLATION_REASON_CUSTOMER_REQUEST`
- `CANCELLATION_REASON_VEHICLE_SOLD`
- `CANCELLATION_REASON_DUPLICATE`
- `CANCELLATION_REASON_ERROR`
- `CANCELLATION_REASON_EXPIRED_EARLY`
- `CANCELLATION_REASON_OTHER`

## Status Values

- `draft` - Editable
- `pending_payment` - Awaiting payment (policies only)
- `active` - In force, immutable
- `cancelled` - Explicitly cancelled
- `expired` - Naturally expired

## Permissions

- **Activate**: Admin, Manager
- **Cancel**: Admin, Manager only
- **Edit**: Only draft/pending_payment
- **Super Admin**: Read-only on business data

## Background Tasks

```python
# In config/celery.py
from celery.schedules import crontab

app.conf.beat_schedule = {
    'expire-compliance-records': {
        'task': 'apps.notifications.tasks.expire_compliance_records',
        'schedule': crontab(hour=1, minute=0),
    },
}
```

## Template Usage

```django
{% if policy.status == 'active' %}
  <span class="badge-green">Active</span>
{% elif policy.status == 'cancelled' %}
  <span class="badge-red">Cancelled</span>
  <p>Cancelled by: {{ policy.cancelled_by.get_full_name }}</p>
  <p>Reason: {{ policy.get_cancellation_reason_display }}</p>
  <p>Note: {{ policy.cancellation_note }}</p>
{% endif %}

{% if not policy.is_immutable %}
  <a href="{% url 'dashboard:policies_update' policy.pk %}">Edit</a>
{% endif %}

{% if policy.status in 'active,pending_payment' and user.role in 'admin,manager' %}
  <a href="{% url 'dashboard:policies_cancel' policy.pk %}">Cancel</a>
{% endif %}
```

## Validation

```python
# Activation validates:
- Status is draft or pending_payment
- Policy: Full payment received
- No overlapping active records
- Tenant permissions

# Cancellation validates:
- Status is not already cancelled/expired
- Reason is provided and valid
- Actor has admin/manager role
- Actor belongs to same tenant
```

## Audit Fields

Every entity tracks:
- `activated_at` - When activated
- `cancelled_at` - When cancelled
- `cancelled_by` - User who cancelled
- `cancellation_reason` - Enum value
- `cancellation_note` - Optional text
- `status` - Current state
- History via `HistoricalRecords`
