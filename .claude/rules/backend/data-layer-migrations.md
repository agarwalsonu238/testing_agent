---
description: Guide data persistence and migration safety in the FastAPI backend (`backend/`).
paths:
  - "backend/**"
---
# Data Layer And Migrations

Guide data persistence and migration safety in the FastAPI backend (`backend/`).

Use this rule during the Plan, Build, Review, Test, and Ship stages.

This project uses an Object-Relational Mapping (ORM) layer to handle persistence. Before changing persistence, identify data model impact, query ownership, migration risk, deployment order, rollback/remediation path, and tests.

## AI Responsibilities

- Identify data model impact before editing.
- Separate schema changes from application logic where the stack supports it.
- Name destructive operations.
- Include rollback notes for migrations.
- Validate data access paths and failure modes.

## AI Must Avoid

- Dropping, renaming, or transforming data without explicit approval.
- Editing applied migrations.
- Hiding migration risk inside implementation details.
- Bypassing repositories or transaction boundaries when conventions exist.
- Persisting sensitive values without encryption, hashing, or masking requirements.
- Changing persistence behavior without tests or manual checks.

## Stack-Specific Guidance

No database is configured yet. Adding one is an architecture decision that needs explicit approval in Plan.
When approved, the default choice is **SQLAlchemy 2.0 (async) + Alembic** on PostgreSQL.

### Repository Pattern
- All queries live in `app/repositories/<resource>.py`. Routes and services never build queries inline.
- Sessions come from an `AsyncSession` dependency (`get_session` in `app/api/deps.py`), one per request.

### Schema & Models
- ORM models in `app/models/`; API schemas (Pydantic) in `app/schemas/`. Never return ORM objects from routes.
- Use `Mapped[...]` / `mapped_column` typed declarations so mypy can check them.

### Migration Conventions
- Every schema change ships with an Alembic revision (`uv run alembic revision --autogenerate -m "<what>"`),
  reviewed by hand — autogenerate misses renames and data moves.
- Destructive steps (drop column/table, type narrowing) are split into expand → migrate → contract releases
  and documented with rollback notes.

### Data Seeding
- Seed scripts are idempotent and live in `backend/scripts/`; never run them automatically on startup.

## Acceptance Criteria

- Data impact is named.
- Migration risk is documented.
- Rollback or remediation path is described.
- Query paths, constraints, indexes, and transactions are reviewed.
- Migration and data-access tests or manual checks are listed.
