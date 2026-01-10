---
trigger: always_on
---

VEHICLE INSURANCE INFORMATION SYSTEM
ENGINEERING & ARCHITECTURE RULES (AUTHORITATIVE)

Status: Mandatory
Applies to: All IDEs, AI assistants, contributors, and future maintainers
Project Type: Multi-Tenant Insurance Information System
Architecture: Modular Monolith (Django)

1. CORE PRINCIPLES (NON-NEGOTIABLE)

This system is a real insurance platform, not a demo.

Correctness > Cleverness.

Clarity > Abstraction.

Security > Convenience.

Maintainability > Speed of initial coding.

No feature is added without a clear business reason.

Any implementation that violates these principles is incorrect, even if it “works”.

2. MULTI-TENANCY RULES (CRITICAL)

Tenant = Insurance Company

Single database, tenant isolation via tenant_id

Every business-critical table MUST:

Contain tenant_id

Enforce tenant-scoped queries

2.1 Absolute Rules

A tenant user MUST NEVER access another tenant’s data.

Cross-tenant queries are forbidden outside Super Admin scope.

No global .objects.all() on tenant data.

2.2 Enforcement

Use tenant-aware model managers.

Apply tenant filtering at:

Query layer

Service layer

View/API layer

Tenant isolation is a security boundary, not a convenience feature.

3. USER TYPES & AUTHORITY MODEL
3.1 User Categories
User Type	Tenant Bound	Purpose
Super Admin	❌ No	Platform governance
Admin	✅ Yes	Tenant configuration
Manager	✅ Yes	Oversight & control
Agent/Staff	✅ Yes	Daily operations
3.2 Super Admin Rules

Super Admin:

Has is_super_admin = true

Has tenant_id = NULL

A user can be Super Admin OR Tenant User, never both

Super Admin:

Must NOT perform tenant business operations

Must NOT create/edit customers, vehicles, policies, or payments

All Super Admin actions MUST be audited

4. DOMAIN RULES (BUSINESS LOGIC)
4.1 Customers

Customers can be Individual or Company

Customers may own multiple vehicles

Customer history MUST be preserved

No hard deletes

4.2 Vehicles

Vehicle belongs to one customer at a time

Vehicle may have multiple policies over time

A vehicle MUST NOT have more than one ACTIVE policy at any moment

This rule must be enforced at:

Database constraints (where possible)

Application logic

Service layer validation

4.3 Policies

Policy activation requires FULL payment

Policies have flexible start/end dates

Renewals extend existing policies

Policy history is immutable

4.4 Payments

Full payment only

No partial payments

No active policy without successful payment

5. DYNAMIC FIELDS RULES

Dynamic fields are allowed for:

Customers

Vehicles

Policies

Dynamic fields MUST be:

Structured

Queryable

Reportable

JSON-only free-form storage is prohibited.

Dynamic fields must be implemented via:

Field definitions

Field values

Field creation is restricted to:

Super Admin

Tenant Admin (within tenant scope)

6. DATA SAFETY & AUDITABILITY

Soft delete only

No destructive deletes on business data

Every mutation must record:

Who did it

When

What entity

Audit logs are immutable

If data disappears, the system has failed.

7. ARCHITECTURE RULES (MODULAR MONOLITH)
7.1 Mandatory Structure

Clear domain-based Django apps

No “everything in one app”

No circular dependencies

7.2 Service Layer

All business rules MUST live in service modules

Views must:

Orchestrate

Validate input

Delegate logic

Business logic in views is forbidden.

8. PERFORMANCE & SCALABILITY

Avoid N+1 queries

Index all foreign keys

Index frequently filtered fields:

tenant_id

status

dates

Background jobs (expiry checks, notifications) MUST use Celery

Reports must be efficient and tenant-scoped

Performance is a feature.

9. SECURITY RULES

No data exposure across tenants

Explicit permission checks everywhere

No silent permission fallbacks

Sensitive actions must be logged

Authentication:

Email + password

Secure hashing

Super Admin access must be restricted and monitored

Security failures are platform failures.

10.UI(Tailwind CSS Usage Rules (Project Standard))

I. Framework Positioning

Tailwind CSS is the only styling framework allowed.

Bootstrap, custom CSS frameworks, and inline <style> blocks are forbidden.

Plain CSS files are allowed only for:

CSS variables

Font imports

Rare global resets not covered by Tailwind

II. Utility-First Discipline

Styling must be done exclusively using Tailwind utility classes.

Do not create semantic CSS classes like .btn-primary, .card, .container.

Repetition of utility classes is acceptable and preferred over abstraction too early.

Reason: premature abstraction recreates Bootstrap problems under a new name.

III. Component Extraction Rule

If a group of Tailwind classes is repeated 3 or more times, extract it into:

A Django template partial, or

A reusable HTML component

Do not extract CSS classes into custom stylesheets.

Correct:

{% include "components/button.html" %}


Incorrect:

.btn-primary { ... }

IV. Layout Rules

All layouts must use:

flex, grid, or responsive utilities

Absolute positioning should be avoided unless unavoidable.

Page structure must follow:

Container

Section

Component

No random nesting chaos.

V. Spacing & Sizing Constraints

Only Tailwind spacing scale is allowed.

Arbitrary values like mt-[13px] are discouraged.

Use arbitrary values only when:

Matching a strict design requirement

Documented with a comment

Consistency beats pixel perfection.

VI. Color Usage

Colors must come from the Tailwind theme configuration.

Hardcoded hex colors in templates are not allowed.

If a new color is needed:

Add it to tailwind.config.js

Use it consistently

This enforces a design system, not vibes.

VII. Responsiveness Rules

Mobile-first approach is mandatory.

Use Tailwind breakpoints explicitly:

sm, md, lg, xl, 2xl

No desktop-only layouts.

If it breaks on mobile, it’s broken. End of story.

VIII. State & Interaction Styling

Always include:

hover

focus

disabled states where relevant

Forms must show clear focus states.

Accessibility is not optional decoration.

IX. Forms & UI Consistency

All forms must follow the same visual patterns:

Input height

Border radius

Focus ring style

Do not invent new form styles per page.

One system. One look.

X. JavaScript Interaction

Tailwind handles visual state only.

JavaScript (or Alpine.js) handles behavior.

Do not mix logic into styling decisions.

Example:

JS toggles hidden

Tailwind controls appearance

XI. Migration Rule (Bootstrap → Tailwind)

Bootstrap classes must be removed, not overridden.

Do not mix Bootstrap and Tailwind in the same template.

Migration is replace, not coexist.

Temporary duplication is allowed only during active refactoring, not committed state.

XII. Performance Rules

Tailwind must run in production mode with purge enabled.

Unused styles must not ship.

The final CSS bundle should remain minimal.

Bloated CSS is considered a defect.

XIII. IDE Behavior Expectations

The IDE must:

Prefer Tailwind utilities over custom CSS

Avoid suggesting Bootstrap equivalents

Avoid generating semantic CSS classes

Encourage reuse through templates, not stylesheets

XIV. Decision Principle

When unsure:

Prefer clarity over cleverness

Prefer duplication over abstraction

Prefer Tailwind utilities over custom CSS

Prefer consistency over creativity

11.UX Rules & Principles (Project Standard)

I. Primary UX Goal

The system must optimize for:

Speed of task completion

Error prevention

Cognitive simplicity

A user should never wonder:

“What am I supposed to do next?”

If they do, the UX failed.

II. Task-First Design Rule

Every page must answer one primary question:

View pages: What is the current state?

Form pages: What action am I performing?

List pages: What can I act on next?

Pages that try to do everything do nothing well.

III. One Primary Action Rule

Each screen may have only one primary action.

Primary action must be:

Visually dominant

Consistently placed

Secondary actions must be visually quieter.

No button democracy. Someone must be in charge.

IV. Progressive Disclosure Rule

Do not show everything at once.

Show essentials first

Hide advanced options behind:

Toggles

Expand sections

Secondary flows

If a feature is not used daily, it should not be visible by default.

V. Form UX Rules (Critical)

Forms are where systems lose users.

Required:

Clear labels (no placeholders as labels)

Explicit required/optional indicators

Inline validation messages

Field grouping by meaning, not layout

Forbidden:

Long vertical forms without sections

Submitting without feedback

Reset buttons next to submit

If a form fails silently, it is broken.

VI. Feedback & System State Rule

Every action must produce immediate feedback.

Examples:

Loading states for async actions

Success confirmation after submit

Clear error explanation on failure

The system must never feel frozen or unsure.

VII. Error Prevention > Error Handling

Prefer:

Constraints

Defaults

Disabled invalid actions

Over:

Letting users fail and apologizing later

Example:

Disable “Create Policy” if vehicle already has an active one

Do not allow the error to happen

VIII. Consistency Over Cleverness

Same action = same placement

Same color = same meaning

Same flow = same steps

If a user learns once, they should reuse that knowledge everywhere.

IX. Navigation UX Rules

Navigation must reflect user mental model, not database structure

Use nouns, not technical terms

Limit top-level navigation items

If you need a tooltip to explain a menu item, rename it.

X. Empty States Are UX, Not Edge Cases

Empty pages must:

Explain what this area is for

Show how to get started

Provide a clear next action

An empty table with no explanation is hostile.

XI. Readability & Scanning Rule

Users scan, they don’t read.

Therefore:

Use headings

Use short labels

Use white space intentionally

Avoid dense paragraphs

If it looks like a document, you failed.

XII. Speed Perception Rule

Perceived speed matters more than actual speed.

Show skeletons or loaders

Disable buttons during processing

Confirm actions instantly, process later when possible

Silence feels like failure.

XIII. Destructive Action Rule

Destructive actions must:

Be visually distinct

Require confirmation

Explain consequences clearly

No vague “Are you sure?” dialogs. Be specific.

XIV. UX Debt Rule

If a UX compromise is made for speed:

It must be documented

It must be intentional

It must be revisited

Accidental bad UX is worse than slow UX.

XV. IDE Enforcement Expectations

The IDE should:

Flag pages with multiple primary CTAs

Encourage reuse of known UX patterns

Avoid generating forms without validation feedback

Avoid placing destructive actions near primary actions

12. CODING STANDARDS

Follow Django best practices strictly

Use meaningful names

No magic values

Explicit > implicit

Comments explain why, not what

Code must be readable by another engineer in 6 months

13. FUTURE-READINESS (DESIGN ONLY)

Design must allow future support for:

SaaS billing

Usage limits

Feature flags

API access

Do NOT implement these yet.

14.IDE / AI ASSISTANT INSTRUCTIONS

Any IDE or AI assistant must:

Respect all rules above

Refuse shortcuts that violate:

Tenant isolation

Security

Data integrity

Explain reasoning for decisions

Prefer long-term correctness over fast output

FINAL AUTHORITY STATEMENT

If there is a conflict between:

Speed and safety → choose safety

Convenience and correctness → choose correctness

Cleverness and clarity → choose clarity