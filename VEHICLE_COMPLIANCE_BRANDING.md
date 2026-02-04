# Vehicle Compliance Branding Implementation

## Overview
This document describes the vehicle-centric compliance branding features implemented to make the system feel authoritative, compliance-driven, and vehicle-first.

## Implementation Date
2024

## Core Philosophy
The system is a **Vehicle Management System (VMS)**, not an insurance system. Vehicles are the root aggregate, and insurance/permits are compliance attributes that orbit the vehicle.

---

## 1. Vehicle Compliance Status (Core Feature)

### Status Levels
The system computes real-time compliance status for each vehicle:

- **Fully Compliant** (Green): Vehicle has all required active records and nothing expiring soon
- **At Risk** (Amber): Vehicle has records expiring within the configured risk window (default 30 days)
- **Non-Compliant** (Red): Vehicle is missing required records or has expired records

### Compliance Rules
Compliance considers:
- Active insurance policy (required)
- Active LATRA registration (if applicable)
- Expiry proximity based on tenant-configurable risk window

### Implementation Location
- **Service**: `apps/core/services/vehicle_compliance_service.py`
  - `compute_compliance_status()` - Computes status for a single vehicle
  - `get_tenant_compliance_summary()` - Aggregates compliance across all tenant vehicles
  
- **Model**: `apps/core/models/vehicle.py`
  - `get_compliance_status()` - Property method for easy access
  - `is_compliant()` - Boolean check for compliance

### Business Logic
```python
# Non-compliant if:
- No active insurance
- Insurance expired
- LATRA expired (if exists)

# At risk if:
- Insurance expires within risk_window_days
- LATRA expires within risk_window_days

# Compliant if:
- Has active insurance
- No expiring records within risk window
```

---

## 2. Compliance-Aware Dashboard

### Dashboard Transformation
The dashboard now answers the critical questions:
- How many vehicles are compliant today?
- How many are at risk?
- How many are non-compliant?

### Visual Design
- **Primary Metrics**: Four cards showing Total, Compliant, At Risk, Non-Compliant
- **Color Coding**: 
  - Emerald (green) for compliant
  - Amber (yellow) for at risk
  - Red for non-compliant
- **Contextual Information**: Each card shows what the status means

### Implementation
- **View**: `apps/core/views.py` - `DashboardHomeView`
- **Template**: `templates/dashboard/home.html`

### Key Changes
- Title changed from "Dashboard" to "Vehicle Compliance Dashboard"
- Subtitle emphasizes "Real-time compliance status for your fleet"
- Primary focus on vehicle compliance, not insurance policies
- Secondary metrics show supporting data (policies, customers)

---

## 3. Vehicle-Centric Language Enforcement

### Terminology Changes

#### Before → After
- "Create Insurance" → "Register Insurance"
- "New Policy" → "Register Insurance"
- "Add Permit" → "Record Permit"
- "New LATRA Record" → "Record LATRA License"
- "Active Policy" → "Active Insurance Coverage"
- "All Policies" → "Insurance History"
- "Period" → "Coverage Period" / "Validity Period"
- "Expiring Soon" → "Vehicles Requiring Attention"

### Authoritative Language Principles
1. **Action-oriented**: Use verbs that imply official recording (Register, Record, Document)
2. **Vehicle-first**: Always frame from vehicle perspective, not insurance perspective
3. **Compliance-focused**: Emphasize legal/regulatory implications
4. **Clear consequences**: State what non-compliance means ("not legal to operate")

### Implementation Locations
- `templates/dashboard/home.html` - Dashboard labels
- `templates/dashboard/vehicle_detail.html` - Vehicle detail page
- Button labels throughout the system

---

## 4. Vehicle Detail Page Enhancements

### Compliance Status Badge
Each vehicle detail page now shows:
- Visual status badge (Fully Compliant / At Risk / Non-Compliant)
- Color-coded with icon
- Positioned prominently below vehicle registration number

### Compliance Alerts
Two types of alerts appear when relevant:

#### Non-Compliance Alert (Red)
- Lists specific issues (e.g., "No active insurance", "Insurance expired")
- Appears at top of page for immediate visibility
- Clear call-to-action

#### At-Risk Alert (Amber)
- Lists items expiring soon with dates
- Proactive warning before non-compliance
- Allows time for renewal

### Tab Language Updates
- Insurance tab emphasizes "Coverage" terminology
- LATRA tab uses "Registration Records"
- Permits tab uses "Regulatory Permits"
- All use "Validity Period" instead of generic "Period"

### Implementation
- **View**: `apps/core/views.py` - `VehicleDetailView`
- **Template**: `templates/dashboard/vehicle_detail.html`

---

## 5. Technical Architecture

### Service Layer
All compliance logic lives in the service layer, not views or templates:

```python
# apps/core/services/vehicle_compliance_service.py

class VehicleComplianceService:
    STATUS_COMPLIANT = 'compliant'
    STATUS_AT_RISK = 'at_risk'
    STATUS_NON_COMPLIANT = 'non_compliant'
    
    @staticmethod
    def compute_compliance_status(*, vehicle, risk_window_days=30):
        # Returns: {'status', 'issues', 'expiring_soon', 'insurance', 'latra'}
        
    @staticmethod
    def get_tenant_compliance_summary(*, tenant, risk_window_days=30):
        # Returns: {'total', 'compliant', 'at_risk', 'non_compliant'}
```

### Model Integration
Vehicle model provides convenient access:

```python
# apps/core/models/vehicle.py

class Vehicle(BaseModel):
    def get_compliance_status(self, risk_window_days=30):
        # Returns status string
        
    def is_compliant(self, risk_window_days=30):
        # Returns boolean
```

### View Integration
Views compute compliance and pass to templates:

```python
# Dashboard view
compliance_summary = VehicleComplianceService.get_tenant_compliance_summary(
    tenant=tenant,
    risk_window_days=risk_days
)

# Vehicle detail view
compliance_status = VehicleComplianceService.compute_compliance_status(
    vehicle=vehicle,
    risk_window_days=risk_days
)
```

---

## 6. Configuration

### Tenant Settings
Risk window is configurable per tenant:

```python
# Default: 30 days
tenant.set_setting('expiry_reminder_days', 30)

# Access in code:
risk_days = tenant.get_setting('expiry_reminder_days', 30)
```

### Extensibility
The compliance system is designed to be extended:
- Additional compliance checks can be added to `compute_compliance_status()`
- New permit types are automatically included
- LATRA logic remains non-hardcoded

---

## 7. Data Integrity

### Immutability
- Historical compliance data is never deleted
- All compliance records use soft deletes
- Audit trails maintained for all changes

### Temporal Integrity
- No overlapping active insurance policies per vehicle
- No overlapping active permits of the same type
- Expiry dates properly validated

### Vehicle-Centric Constraints
- Insurance always references Vehicle (never the reverse)
- Permits always reference Vehicle
- Vehicle exists independently of compliance records

---

## 8. User Experience Impact

### What Users See
1. **Login** → Immediate compliance dashboard showing fleet status
2. **Dashboard** → Clear counts of compliant/at-risk/non-compliant vehicles
3. **Vehicle Detail** → Instant compliance status with specific issues
4. **Proactive Alerts** → Warnings before records expire

### What Users Understand
- Which vehicles are legal to operate today
- Which vehicles need attention soon
- Why a vehicle is non-compliant
- What action to take

### Authoritative Feel
- Professional terminology (Register, Record, Document)
- Clear legal implications ("not legal to operate")
- Compliance-first mindset throughout
- Vehicle as the central entity

---

## 9. Success Metrics

### System Behavior
✅ Vehicle is the root entity in all flows
✅ No insurance-first navigation
✅ Compliance status computed in real-time
✅ Historical data preserved
✅ Extensible permit system

### User Experience
✅ Immediate understanding of fleet compliance
✅ Clear action items for non-compliant vehicles
✅ Proactive warnings before expiry
✅ Authoritative, professional language

---

## 10. Future Enhancements (Not Implemented)

### Potential Extensions
- Email/SMS alerts for expiring records
- Compliance reports by vehicle type
- Compliance trends over time
- Bulk compliance actions
- Compliance dashboard filters

### Design Considerations
- All extensions must maintain vehicle-centric architecture
- Compliance logic stays in service layer
- Historical data remains immutable
- Permit types remain extensible

---

## 11. Testing Recommendations

### Compliance Status Tests
```python
# Test compliant vehicle
vehicle = create_vehicle_with_active_insurance()
assert vehicle.is_compliant() == True

# Test at-risk vehicle
vehicle = create_vehicle_with_expiring_insurance(days=15)
assert vehicle.get_compliance_status() == 'at_risk'

# Test non-compliant vehicle
vehicle = create_vehicle_without_insurance()
assert vehicle.get_compliance_status() == 'non_compliant'
```

### Dashboard Tests
- Verify compliance counts are accurate
- Test with various tenant risk windows
- Ensure vehicle-centric language appears

### Integration Tests
- Full flow: Create vehicle → Register insurance → Check compliance
- Expiry flow: Active insurance → Time passes → Status changes
- Multi-vehicle: Multiple vehicles with different statuses

---

## 12. Maintenance Notes

### Code Locations
- **Compliance Service**: `apps/core/services/vehicle_compliance_service.py`
- **Vehicle Model**: `apps/core/models/vehicle.py`
- **Dashboard View**: `apps/core/views.py` - `DashboardHomeView`
- **Vehicle Detail View**: `apps/core/views.py` - `VehicleDetailView`
- **Dashboard Template**: `templates/dashboard/home.html`
- **Vehicle Detail Template**: `templates/dashboard/vehicle_detail.html`

### Key Principles to Maintain
1. Vehicle is always the root aggregate
2. Compliance logic lives in service layer
3. Historical data is immutable
4. Language is authoritative and vehicle-first
5. Permit types remain extensible

### What NOT to Do
❌ Don't make insurance the primary entity
❌ Don't hardcode LATRA logic
❌ Don't delete historical compliance data
❌ Don't allow multiple active insurance per vehicle
❌ Don't use generic CRUD language

---

## 13. Architectural Compliance Checklist

When adding new features, verify:

- [ ] Does this feature start from Vehicle?
- [ ] Can this support new permit types without refactoring?
- [ ] Is historical data preserved and immutable?
- [ ] Does the language emphasize vehicle-first perspective?
- [ ] Are compliance rules enforced at service layer?
- [ ] Is the UI authoritative and compliance-focused?

---

## Conclusion

This implementation transforms the system from a generic insurance platform into an authoritative Vehicle Management System with compliance intelligence. The vehicle-centric architecture, real-time compliance status, and authoritative language create a professional, regulatory-aware experience without adding marketing fluff or visual polish.

The system now clearly communicates:
- **What**: Which vehicles are compliant
- **When**: When vehicles will become non-compliant
- **Why**: What specific issues exist
- **How**: What actions to take

All while maintaining architectural integrity, data immutability, and extensibility for future regulatory requirements.
