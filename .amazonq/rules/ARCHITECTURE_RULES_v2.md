# Vehicle Management System (VMS)
## Authoritative Architecture & Domain Rules

Status: Mandatory  
Scope: Architecture, domain modeling, system evolution  
Applies to: All IDEs, AI assistants, contributors, and maintainers

---

## 1. System Reorientation (Non-Negotiable)

The system is vehicle-centric, not insurance-centric.

- A Vehicle is the core aggregate root.
- Insurance, LATRA, permits, inspections, and ownership records orbit the vehicle.
- Any design that treats Insurance as the primary entity is incorrect.

---

## 2. Core Domain Aggregates

### 2.1 Vehicle (Primary Aggregate Root)

Each vehicle MUST have:
- Unique identifier (UUID)
- Registration number (plate)
- Chassis number
- Engine number
- Vehicle type (private, commercial, motorcycle, truck, etc.)
- Usage category (private, public transport, cargo, rental)
- Status (active, suspended, retired)

Rules:
- A vehicle exists independently of insurance or permits.
- A vehicle is the long-lived entity to which all compliance data attaches.

---

### 2.2 Insurance (Sub-Domain)

Insurance records:
- Belong to exactly one vehicle
- Have validity periods (start and end)
- May be historical (expired, cancelled)

Rules:
- A vehicle may have zero or many insurance records
- Only one insurance record may be ACTIVE at any time per vehicle
- Insurance never owns or defines the vehicle
- Insurance is a compliance attribute, not a root entity

---

### 2.3 LATRA & Regulatory Permits (Sub-Domain)

The system must support multiple permit types, including but not limited to:
- LATRA road license
- Route permit
- PSV badge
- Inspection certificate
- Temporary permits

Rules:
- Permits are always vehicle-bound
- Permit types must be extensible and data-driven
- Permit logic must not be hardcoded

Each permit MUST include:
- Issuing authority
- Issue date
- Expiry date
- Status (valid, expired, revoked)

---

### 2.4 Ownership & Assignment

Vehicles may be:
- Owned by individuals
- Owned by companies
- Assigned to drivers or employees

Rules:
- Ownership history MUST be preserved
- Assignment does not imply ownership
- A vehicle may exist without an active owner record
- Ownership and assignment are separate concepts

---

## 3. Temporal Integrity Rules

Time is a first-class constraint.

Rules:
- No overlapping validity periods for insurance
- No overlapping validity periods for same-type permits
- Historical records are immutable
- Edits create new versions or records
- Silent overwrites of historical data are forbidden

---

## 4. Data Modeling Rules

- Vehicle is the foreign key anchor for compliance data
- Circular dependencies are forbidden
- Prefer OneToMany relationships for:
  - Insurance records
  - Permit records
  - Inspections
- Use ManyToMany only when unavoidable and well-justified
- Regulatory and financial records must use soft deletes

---

## 5. Application Layer Responsibilities

The system MUST provide:
- Vehicle compliance status aggregation
  - Insurance state
  - Permit state
- Expiry alerts via background processing
- Historical audit trails
- Role-based access control

Supported roles:
- Admin
- Company manager
- Officer / staff
- Read-only auditor

---

## 6. Scalability & Extensibility Rules

- New permit types must require zero schema rewrites
- Regulatory authorities must be configurable
- Country-specific rules must be isolated
- Core domain logic must remain jurisdiction-agnostic

---

## 7. What This System Is NOT

This system is NOT:
- An insurance sales platform
- A payment gateway
- A government system replacement

It IS:
- A vehicle lifecycle system
- A compliance intelligence platform
- A regulatory-awareness tool for operators

---

## 8. Failure Conditions (Instant Rejection)

Any implementation that:
- Treats insurance as the root entity
- Hardcodes LATRA logic
- Deletes historical compliance data
- Allows multiple active insurance records per vehicle

Is architecturally invalid and must be rejected.
