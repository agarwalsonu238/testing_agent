---
name: build
description: "Build stage of the lifecycle (Think → Plan → Build → Review → Test → Ship → Reflect) for this Next.js + FastAPI monorepo: implement only the approved scope. Use when the user invokes /build or a non-trivial change reaches this stage."
---

# Build

This repo has two apps. Decide which side(s) the change touches, then apply the matching section(s).
If both are touched, apply both, and also check the **API contract** between them
(`backend/src/app/api/` ↔ `frontend/src/lib/api.ts`): request/response shapes, status codes, and `/api/v1` paths must stay in sync.

- Frontend rules: `.claude/rules/frontend/` · context: `frontend/CLAUDE.md`
- Backend rules: `.claude/rules/backend/` · context: `backend/CLAUDE.md`

## Frontend (`frontend/`)

### Stage Goal

Implement only the approved plan scope while preserving project conventions. Do not widen scope during Build.

### Inputs Needed

- Approved plan or clear small request.
- Relevant files, components, hooks, and tests.
- Existing component, styling, routing, state, and data-fetching patterns already in the repo.
- Local project commands sourced from your project's AGENT documentation.

### AI Behavior Expected

- Make focused changes only in the files named by the plan.
- Reuse existing components, hooks, styles, utilities, and test helpers.
- Keep state close to the consuming UI unless sharing or persistence requires otherwise.
- Preserve accessibility semantics, loading/error/empty states, and responsive layout.
- Add or update tests/docs only where the behavior changes.

### AI Behavior Forbidden

- Unrelated UI rewrites or broad folder restructuring.
- Speculative abstractions for one-off screens or components.
- Silent route, state, API, or accessibility behavior changes.
- Adding dependencies without a clear need and an approval path.
- Expanding scope beyond the approved plan.

### Output Expected

- Focused code or documentation changes inside the planned file impact map.
- Updated tests or validation notes where the behavior changes.
- No unrelated churn.

### Quality Bar

Build is complete when the planned behavior exists, scope boundaries were respected, and the change is ready for review and validation.

## Backend (`backend/`)

### Stage Goal

Implement only the approved backend scope while preserving existing contracts, data safety, security boundaries, and project conventions. Do not widen scope during Build.

### Inputs Needed

- Approved plan or clear small request.
- Relevant source files, tests, migrations, fixtures, and local commands.
- Your project's rule guidance for architecture, API, data, security, integrations, async work, and testing.

### AI Behavior Expected

- Make focused changes that match existing FastAPI router/service/schema patterns.
- Keep transport, business logic, persistence, and external integration boundaries aligned with the repo.
- Preserve public API contracts unless the plan explicitly changes them.
- Add or update validation, errors, logging, tests, and docs when required by the change.
- Keep migrations separate and reversible where the stack supports it.

### AI Behavior Forbidden

- Broad cleanup outside the approved task.
- Silent response shape, auth, authorization, or persistence behavior changes.
- Destructive migrations without explicit approval and rollback / remediation notes.
- Direct third-party calls from unrelated layers when wrappers exist.
- New dependencies without approval.
- Auth or authorization changes without explicit review.

### Output Expected

- Focused backend changes inside the planned impact map.
- Updated tests, docs, or validation notes where applicable.
- No unrelated churn.

### Quality Bar

Build is complete when the planned backend behavior exists, risk boundaries were respected, and the work is ready for review and validation.
