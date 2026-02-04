---
trigger: always_on
---

Short, Enforceable Rules for IDE / AI / Copilot

Think of this as a stop sign. Miss one, you’re wrong.

CORE RULES

Vehicle is the root model. Always.

No model owns a vehicle except Vehicle itself.

Insurance and permits reference vehicles, never the reverse.

DATA RULES

No overlapping active records per vehicle per category

Expired records are never deleted

Use UUIDs, not auto-increment IDs

DOMAIN RULES

Insurance ≠ Vehicle

Permit types must be dynamic

Ownership history is immutable

DESIGN RULES

No hardcoding LATRA logic

No country rules in core domain

Background jobs handle expiry & alerts

FORBIDDEN

Insurance-centric schema

Single “permit” table with magic strings

Deleting compliance history

Mixing auth logic with domain logic

REQUIRED CHECKS

Before merging code:

Does this feature start from Vehicle?

Can this support a new permit type without refactor?

Is history preserved?

If the answer is “no”, stop.