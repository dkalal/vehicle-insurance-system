# Vehicle-Centric Language Guide

## Quick Reference for Developers & Content Writers

### Core Principle
**The system is vehicle-centric, not insurance-centric.**
Always frame features from the vehicle's perspective.

---

## Terminology Standards

### ✅ USE (Vehicle-First)
- Register Insurance
- Record LATRA License
- Record Permit
- Active Insurance Coverage
- Insurance History
- Coverage Period
- Validity Period
- Vehicles Requiring Attention
- Vehicle Compliance Dashboard
- Regulatory Permits
- LATRA Registration Records
- Not legal to operate
- Compliance status
- Vehicle is compliant
- Vehicle requires attention

### ❌ AVOID (Insurance-First)
- Create Insurance
- Add Insurance
- New Policy
- Add Permit
- New LATRA Record
- Active Policy
- All Policies
- Period
- Expiring Soon
- Dashboard
- Permits
- LATRA Records
- Invalid
- Policy status
- Policy is active
- Policy needs renewal

---

## Button Labels

### Insurance Actions
- ✅ "Register Insurance" (not "Create Policy")
- ✅ "Renew Coverage" (not "Renew Policy")
- ✅ "View Coverage" (not "View Policy")

### LATRA Actions
- ✅ "Record LATRA License" (not "Add LATRA")
- ✅ "Update Registration" (not "Edit Record")

### Permit Actions
- ✅ "Record Permit" (not "Add Permit")
- ✅ "Update Permit" (not "Edit Permit")

---

## Status Messages

### Compliance Status
- ✅ "Fully Compliant" - Vehicle meets all requirements
- ✅ "At Risk" - Records expiring soon
- ✅ "Non-Compliant" - Missing or expired records

### User Feedback
- ✅ "Insurance registered successfully"
- ❌ "Policy created successfully"

- ✅ "LATRA license recorded"
- ❌ "LATRA record added"

- ✅ "Vehicle is now compliant"
- ❌ "Policy is now active"

---

## Page Titles

### Dashboard
- ✅ "Vehicle Compliance Dashboard"
- ❌ "Dashboard" or "Insurance Dashboard"

### Vehicle Pages
- ✅ "Vehicle [Registration]"
- ✅ "Register Vehicle"
- ❌ "Add Vehicle" or "Create Vehicle"

### Insurance Pages
- ✅ "Register Insurance Coverage"
- ✅ "Insurance History"
- ❌ "Create Policy" or "Policy List"

---

## Section Headers

### Vehicle Detail Page
- ✅ "Active Insurance Coverage" (not "Active Policy")
- ✅ "Insurance History" (not "All Policies")
- ✅ "LATRA Registration Records" (not "LATRA Records")
- ✅ "Regulatory Permits" (not "Permits")

### Dashboard
- ✅ "Vehicles Requiring Attention" (not "Expiring Soon")
- ✅ "Fleet Compliance Status" (not "Policy Status")

---

## Alert Messages

### Non-Compliance
- ✅ "No active insurance coverage. Vehicle is not legal to operate."
- ❌ "No active policy for this vehicle."

### At Risk
- ✅ "Insurance expires [date]. Renew coverage to maintain compliance."
- ❌ "Policy expires [date]. Renew policy."

### Success
- ✅ "Vehicle is now fully compliant."
- ❌ "Policy activated successfully."

---

## Form Labels

### Insurance Forms
- ✅ "Coverage Period" (not "Policy Period")
- ✅ "Premium Amount" (acceptable)
- ✅ "Coverage Amount" (acceptable)

### LATRA Forms
- ✅ "Validity Period" (not "Period")
- ✅ "License Type" (not "Type")
- ✅ "Registration Number" (not "LATRA Number")

### Permit Forms
- ✅ "Permit Type" (acceptable)
- ✅ "Validity Period" (not "Period")
- ✅ "Reference Number" (acceptable)

---

## Navigation Labels

### Main Menu
- ✅ "Vehicles" (primary)
- ✅ "Customers" (secondary)
- ✅ "Compliance" (if needed)
- ❌ "Policies" (as primary nav)

### Breadcrumbs
- ✅ Vehicles > [Registration] > Insurance
- ❌ Policies > [Policy Number]

---

## Table Headers

### Vehicle Lists
- ✅ "Registration" (not "Plate")
- ✅ "Compliance Status" (not "Status")
- ✅ "Coverage Expires" (not "Policy Expires")

### Insurance Lists
- ✅ "Coverage Period" (not "Period")
- ✅ "Vehicle" (always show vehicle reference)

---

## Code Comments

### Service Layer
```python
# ✅ Good
def register_insurance_coverage(vehicle, start_date, end_date):
    """Register insurance coverage for a vehicle."""
    
# ❌ Bad
def create_policy(vehicle, start_date, end_date):
    """Create a new policy."""
```

### Model Methods
```python
# ✅ Good
vehicle.get_compliance_status()
vehicle.is_compliant()

# ❌ Bad
policy.is_active()
policy.get_status()
```

---

## API Endpoints (Future)

### RESTful Routes
- ✅ `/api/vehicles/{id}/insurance/`
- ✅ `/api/vehicles/{id}/compliance/`
- ❌ `/api/policies/`
- ❌ `/api/insurance/`

---

## Email/Notification Templates

### Subject Lines
- ✅ "Vehicle [Registration] Requires Attention"
- ✅ "Insurance Coverage Expiring Soon"
- ❌ "Policy Expiring Soon"

### Body Text
- ✅ "Your vehicle [registration] has insurance coverage expiring on [date]."
- ❌ "Your policy [number] is expiring on [date]."

---

## Error Messages

### Validation Errors
- ✅ "Vehicle already has active insurance coverage"
- ❌ "Policy already exists for this vehicle"

- ✅ "Insurance coverage period is invalid"
- ❌ "Policy dates are invalid"

### Permission Errors
- ✅ "You don't have access to this vehicle"
- ❌ "You don't have access to this policy"

---

## Help Text

### Form Help Text
- ✅ "Select the vehicle to register insurance coverage for"
- ❌ "Select the vehicle for this policy"

- ✅ "Coverage period must not overlap with existing active coverage"
- ❌ "Policy period must not overlap with existing policies"

---

## Compliance Language

### Status Descriptions
- **Fully Compliant**: "All required records are active and valid"
- **At Risk**: "One or more records expiring within [X] days"
- **Non-Compliant**: "Missing required records or expired coverage"

### Action Language
- ✅ "Register insurance to restore compliance"
- ✅ "Renew coverage before expiry"
- ✅ "Record LATRA license to complete registration"
- ❌ "Add policy to activate vehicle"

---

## Reporting Language

### Report Titles
- ✅ "Vehicle Compliance Report"
- ✅ "Fleet Status Summary"
- ❌ "Policy Report"
- ❌ "Insurance Report"

### Report Sections
- ✅ "Compliant Vehicles"
- ✅ "Vehicles at Risk"
- ✅ "Non-Compliant Vehicles"
- ❌ "Active Policies"
- ❌ "Expired Policies"

---

## When in Doubt

Ask yourself:
1. **Is this vehicle-first?** Does it frame from the vehicle's perspective?
2. **Is this authoritative?** Does it sound official and compliance-focused?
3. **Is this clear?** Does it explain consequences and actions?

If the answer to any is "no", rephrase.

---

## Examples in Context

### ✅ Good Flow
1. User navigates to "Vehicles"
2. Clicks on vehicle registration number
3. Sees "Compliance Status: At Risk"
4. Reads "Insurance expires in 15 days"
5. Clicks "Renew Coverage"
6. Completes form titled "Register Insurance Coverage"
7. Sees "Insurance registered successfully. Vehicle is now compliant."

### ❌ Bad Flow
1. User navigates to "Policies"
2. Clicks on policy number
3. Sees "Status: Active"
4. Reads "Policy expires in 15 days"
5. Clicks "Renew Policy"
6. Completes form titled "Create New Policy"
7. Sees "Policy created successfully"

---

## Enforcement

### Code Review Checklist
- [ ] All user-facing text uses vehicle-first language
- [ ] Button labels use authoritative verbs (Register, Record)
- [ ] Status messages emphasize compliance, not policy state
- [ ] Error messages reference vehicles, not policies
- [ ] Help text explains from vehicle perspective

### Pull Request Template
When submitting UI changes, confirm:
- "I have reviewed all user-facing text for vehicle-centric language"
- "I have used authoritative terminology (Register, Record, Document)"
- "I have avoided insurance-first framing"

---

## Resources

- Full documentation: `VEHICLE_COMPLIANCE_BRANDING.md`
- Architecture rules: `.amazonq/rules/ARCHITECTURE_RULES_v2.md`
- Service layer: `apps/core/services/vehicle_compliance_service.py`

---

**Remember**: The system manages vehicles and their compliance. Insurance is just one compliance attribute, not the primary entity.
