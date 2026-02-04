# VEHICLE COMPLIANCE & INSURANCE INFORMATION SYSTEM  
## ENGINEERING & ARCHITECTURE RULES (AUTHORITATIVE)

Status: Mandatory  
Applies to: All IDEs, AI assistants, contributors, and future maintainers  
Project Type: Multi-Tenant Vehicle Compliance Platform  
Architecture: Modular Monolith (Django)

---

## 1. CORE PRINCIPLES (NON-NEGOTIABLE)

This system is a real-world, regulated vehicle compliance platform, not a demo.

- Correctness > Cleverness  
- Clarity > Abstraction  
- Security > Convenience  
- Maintainability > Speed  
- Backward Compatibility > Refactor Ego  

No feature is added without a clear business or regulatory reason.

Breaking working systems in the name of “clean code” is a failure.

---

## 2. MULTI-TENANCY RULES (CRITICAL)

### Definition

Tenant = Operating Organization  
(e.g. insurance company, fleet operator, regulator-integrated client)

- Single database  
- Shared schema  
- Row-level isolation via `tenant_id`

Every business-critical table MUST:
- Contain `tenant_id`
- Enforce tenant-scoped access

### 2.1 Absolute Rules

- A tenant user MUST NEVER access another tenant’s data
- Cross-tenant access is forbidden outside Super Admin scope
- No unscoped `.objects.all()` on tenant data
- Tenant isolation is a security boundary, not a convenience feature

### 2.2 Enforcement Layers (ALL REQUIRED)

- ORM managers  
- Service layer  
- Views / APIs  
- Background tasks  
- Reports  

If isolation fails in any one layer, the system is incorrect.

---

## 3. USER TYPES & AUTHORITY MODEL

### 3.1 User Categories

| User Type        | Tenant Bound | Purpose                  |
|------------------|--------------|--------------------------|
| Super Admin      | No           | Platform governance      |
| Admin            | Yes          | Tenant configuration     |
| Manager          | Yes          | Oversight & approvals    |
| Agent / Staff    | Yes          | Daily operations         |

### 3.2 Super Admin Rules

Super Admin:
- `is_super_admin = true`
- `tenant_id = NULL`

Rules:
- A user is either Super Admin or Tenant User, never both

Super Admin MUST NOT:
- Create or modify customers
- Create or modify vehicles
- Create or modify policies, permits, LATRA, or payments

All Super Admin actions MUST be audited.

Super Admin manages the platform, not the business data.

---

## 4. DOMAIN RULES (BUSINESS LOGIC)

### 4.1 Customers

- Customer may be Individual or Company
- Customer may own multiple vehicles
- Ownership history MUST be preserved
- No hard deletes
- Customer history is immutable

### 4.2 Vehicles (PRIMARY DOMAIN ANCHOR)

Vehicle is the core entity of the system.

Rules:
- A vehicle belongs to one customer at a time
- Ownership changes MUST be historically tracked
- A vehicle may have multiple compliance records over time
- Vehicle is the navigation root, not insurance or permits

### 4.3 Vehicle Records (COMPLIANCE LAYER)

Includes:
- Insurance policies
- LATRA registrations
- Road licenses
- Inspections
- Special permits

Rules:
- All records are tenant-scoped
- All records are time-bound (start/end)
- All records have a lifecycle status
- Conflicting records MUST NOT overlap silently

### 4.4 Insurance Policies (INSURANCE MODULE)

Rules:
- A vehicle MUST NOT have more than one ACTIVE insurance policy
- Policy activation requires FULL payment
- Partial payments are forbidden
- Renewals extend existing coverage
- Policy history is immutable

Enforcement required at:
- Database level (where feasible)
- Service layer
- UI level

### 4.5 LATRA Records

- Independent of insurance
- Linked directly to Vehicle
- Must support registration number, license type, route, validity period
- Full audit and history required

### 4.6 Permits

- Permit types are data-driven
- Conflict rules enforced in service layer
- Multiple permits allowed if non-conflicting
- Expiration must be trackable and reportable

### 4.7 Payments

- Payments apply only to Insurance Policies
- Full payment only
- No active policy without confirmed payment
- Payment history is immutable

---

## 5. DYNAMIC FIELDS RULES

Allowed for:
- Customers
- Vehicles
- Insurance Policies
- Vehicle Records

Rules:
- Must be structured, queryable, and reportable
- Free-form JSON blobs are prohibited

Implementation requires:
- Field definitions
- Field values
- Typed storage

Field creation restricted to:
- Super Admin
- Tenant Admin (tenant-scoped)

---

## 6. DATA SAFETY & AUDITABILITY

- Soft delete only
- No destructive deletes on business data

Every mutation MUST record:
- Who
- When
- What
- Tenant context

Audit logs are immutable.

If data disappears, the system has failed.

---

## 7. ARCHITECTURE RULES (MODULAR MONOLITH)

### 7.1 Structure

- Domain-based Django apps
- No god apps
- No circular dependencies
- Clear separation between domain, services, UI, infrastructure

### 7.2 Service Layer (MANDATORY)

- ALL business logic lives in services
- Views validate input and orchestrate flow
- Business logic in views is forbidden

### 7.3 Refactoring Rule (CRITICAL)

- No destructive refactors
- No renaming models or tables without migration strategy
- No breaking existing service contracts
- New functionality must be additive
- Legacy behavior remains until explicitly deprecated

Breaking production logic is a defect.

---

## 8. PERFORMANCE & SCALABILITY

- Avoid N+1 queries
- Index tenant_id, vehicle_id, status, start/end dates
- Background jobs MUST use Celery
- Reports must be tenant-scoped and efficient

Performance is a feature.

---

## 9. SECURITY RULES

- Explicit permission checks everywhere
- No silent fallbacks
- Sensitive actions must be logged

Authentication requires:
- Secure hashing
- Rate limiting
- Session hardening

Super Admin access must be monitored.

---

## 10. UI RULES (TAILWIND CSS)

- Tailwind CSS only
- No Bootstrap
- No semantic CSS
- Utility-first discipline
- Mobile-first
- Accessible by default

Violations mean the UI is incorrect.

---

## 11. UX RULES

- Task-first design
- One primary action per screen
- Progressive disclosure
- Strong form UX
- Clear feedback
- Error prevention over error handling

Confusing UX is a functional bug.

---

## 12. CODING STANDARDS

- Django best practices only
- Explicit over implicit
- Meaningful names
- No magic values
- Comments explain why, not what

Code must be understandable after six months.

---

## 13. FUTURE-READINESS (DESIGN ONLY)

Design must allow for:
- SaaS billing
- Feature flags
- Usage limits
- API access
- Regulatory integrations

Do not implement yet.

---

## 14. IDE / AI ASSISTANT INSTRUCTIONS

Any IDE or AI assistant MUST:
- Respect all rules above
- Refuse shortcuts that violate tenant isolation, security, data integrity, or backward compatibility
- Explain reasoning
- Prefer long-term correctness over speed

---

## FINAL AUTHORITY

When conflicts arise:
- Safety over speed
- Correctness over convenience
- Clarity over cleverness
- Stability over refactoring desire

This document is authoritative.
