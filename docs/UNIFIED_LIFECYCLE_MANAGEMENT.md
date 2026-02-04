# Unified Lifecycle Management for Policies & Vehicle Permits

## Overview

This feature implements a **shared, immutable lifecycle pattern** for all compliance artifacts (Insurance Policies and Vehicle Permits) in the Vehicle Management System. It enforces legal correctness, auditability, and historical accuracy.

## Core Principles

1. **Vehicle-Centric**: All compliance artifacts orbit the vehicle
2. **Immutability After Activation**: Active records cannot be edited
3. **Explicit State Transitions**: All changes are audited state transitions
4. **No Hard Deletes**: Historical data is preserved forever
5. **Time-Aware Compliance**: Historical active windows are respected

## Lifecycle States

All compliance artifacts support these states:

- **draft**: Initial state, editable
- **pending_payment**: (Policies only) Awaiting payment
- **active**: In force, immutable
- **cancelled**: Explicitly cancelled, preserves history
- **expired**: Naturally expired at end_date

## State Transition Rules

```
draft → active (via activation)
pending_payment → active (via activation, policies only)
active → cancelled (via cancellation)
active → expired (via background job)
```

**Forbidden transitions:**
- Cannot edit active records
- Cannot delete any records
- Cannot reactivate cancelled/expired records

## Service Layer API

### Activation
```python
from apps.core.services import lifecycle_service
from apps.core.models.policy import Policy

policy = lifecycle_service.activate_entity(
    entity_id=policy.id,
    actor=request.user,
    model_class=Policy
)
```

### Cancellation
```python
policy = lifecycle_service.cancel_entity(
    entity_id=policy.id,
    actor=request.user,
    reason=Policy.CANCELLATION_REASON_CUSTOMER_REQUEST,
    note="Customer requested cancellation",
    model_class=Policy
)
```

### Time-Aware Queries
```python
start, end = lifecycle_service.get_active_window(policy)
was_active = lifecycle_service.is_active_at(policy, check_date)
```

## Cancellation Reasons

### Policies
- `customer_request`
- `non_payment`
- `vehicle_sold`
- `duplicate`
- `data_error`
- `other`

### Permits
- `customer_request`
- `vehicle_sold`
- `duplicate`
- `data_error`
- `expired_early`
- `other`

## Architecture Compliance

✅ Vehicle is the root entity  
✅ No hard deletes on compliance data  
✅ Immutability after activation  
✅ Explicit state transitions only  
✅ Complete audit trails  
✅ Tenant isolation enforced  
✅ Permission checks at service layer  
✅ Time-aware compliance logic  
✅ Historical data preserved  

## Testing

Run tests:
```bash
pytest apps/core/tests/test_lifecycle_management.py -v
```
