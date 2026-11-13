---
name: test
description: "Test stage of the lifecycle (Think → Plan → Build → Review → Test → Ship → Reflect) for this Next.js + FastAPI monorepo: run or define validation proportional to risk. Use when the user invokes /test or a non-trivial change reaches this stage."
---

# Test

This repo has two apps. Decide which side(s) the change touches, then apply the matching section(s).
If both are touched, apply both, and also check the **API contract** between them
(`backend/src/app/api/` ↔ `frontend/src/lib/api.ts`): request/response shapes, status codes, and `/api/v1` paths must stay in sync.

- Frontend rules: `.claude/rules/frontend/` · context: `frontend/CLAUDE.md`
- Backend rules: `.claude/rules/backend/` · context: `backend/CLAUDE.md`

## Frontend (`frontend/`)

### Stage Goal

Run or define unit, component, integration, and manual checks proportional to risk. State untested areas explicitly. Do not ship without a visible test result.

### Inputs Needed

- Changed behavior and affected user flows.
- Project commands sourced from your project's AGENT documentation.
- Acceptance criteria.
- Manual QA requirements.
- Adapter output paths when generated instructions changed.

### AI Behavior Expected

- Run targeted tests first, then broaden when shared behavior changed.
- Use component/unit tests for logic and rendering branches.
- Use end-to-end (E2E) smoke checks for critical navigation, forms, auth, and data flows.
- Include accessibility checks (keyboard path, focus, screen-reader announcements) for changed interactive UI.
- Define manual checks when automation is missing.
- State untested areas plainly.

### AI Behavior Forbidden

- Claiming tests passed without running them.
- Hiding skipped checks.
- Treating screenshots as a substitute for behavior validation.
- Marking template or adapter changes done without generated-output review.

### Output Expected

- Commands run and results.
- Manual QA checklist if needed.
- Untested areas.
- Release-blocking issues, if any.

### Quality Bar

Test is complete when validation is proportional to risk and gaps are visible to reviewers.

## Backend (`backend/`)

### Stage Goal

Run or define unit, integration, contract, migration, and smoke checks as appropriate for the backend change. State untested areas explicitly.

### Inputs Needed

- Changed behavior or documentation scope.
- Project commands sourced from your project's AGENT documentation.
- Acceptance criteria.
- Manual QA needs.
- Adapter output paths, if generated instructions changed.

### AI Behavior Expected

- Run targeted tests first, then broaden when shared behavior, API contracts, migrations, auth, integrations, or generated output changed.
- Include unit, integration, contract, end-to-end (E2E), migration, and smoke checks as appropriate.
- Verify failure paths for validation, auth denial, missing data, external failures, retries, and idempotency where relevant.
- Define manual checks when automation is missing.
- State untested areas plainly.

### AI Behavior Forbidden

- Claiming tests passed without running them.
- Hiding skipped tests or unavailable environments.
- Treating unit tests as enough for public API, data, auth, or integration changes.
- Marking templates shipped without CLI and adapter smoke checks.

### Output Expected

- Commands run and results.
- Manual QA checklist if needed.
- Untested areas.
- Release-blocking issues, if any.

### Quality Bar

Test is complete when validation is proportional to backend risk and any gaps are visible to the reviewer.
