# IDE GUARDRAILS v2 (LINT RULES)
## Short, Enforceable Rules for IDEs, AI Assistants, and Copilots

Purpose:  
These rules act as hard stop signs.  
If any rule is violated, the implementation is wrong.

---

## CORE RULES

- Vehicle is the root model. Always.
- No model owns a vehicle except Vehicle itself.
- Insurance and permits reference Vehicle.
- Vehicle never references Insurance or Permits directly.

---

## DATA RULES

- No overlapping ACTIVE records per vehicle per category.
- Expired or historical records are never deleted.
- Use UUIDs, not auto-increment IDs.
- Vehicle is the foreign key anchor for compliance data.

---

## DOMAIN RULES

- Insurance is not a Vehicle.
- Permit types must be dynamic and data-driven.
- Ownership history is immutable.
- Assignment does not imply ownership.

---

## DESIGN RULES

- No hardcoded LATRA logic.
- No country-specific rules in the core domain.
- Background jobs handle:
  - Expiry checks
  - Alerts
  - Notifications
- Business rules live in services, not views or serializers.

---

## FORBIDDEN

Any implementation that includes:
- Insurance-centric schemas
- Single generic “permit” table using magic strings
- Deleting compliance or regulatory history
- Mixing authentication logic with domain logic
- Business rules embedded in UI or API layers

Is invalid.

---

## REQUIRED CHECKS (BEFORE MERGE)

Before accepting any change, confirm:

- Does this feature start from Vehicle?
- Can this support a new permit type without refactoring?
- Is historical data preserved and immutable?

If any answer is “no”, stop and reject the change.
