---
name: think
description: "Think stage of the lifecycle (Think → Plan → Build → Review → Test → Ship → Reflect) for this Next.js + FastAPI monorepo: understand the goal, constraints, and existing code before planning. Use when the user invokes /think or a non-trivial change reaches this stage."
---

# Think

This repo has two apps. Decide which side(s) the change touches, then apply the matching section(s).
If both are touched, apply both, and also check the **API contract** between them
(`backend/src/app/api/` ↔ `frontend/src/lib/api.ts`): request/response shapes, status codes, and `/api/v1` paths must stay in sync.

- Frontend rules: `.claude/rules/frontend/` · context: `frontend/CLAUDE.md`
- Backend rules: `.claude/rules/backend/` · context: `backend/CLAUDE.md`

## Frontend (`frontend/`)

### Stage Goal

Understand the user goal, selected frontend stack, constraints, and existing code before proposing any design or implementation work. Name affected routes, components, state boundaries, and accessibility concerns before recommending changes.

### Inputs Needed

- User request and acceptance criteria.
- Project stack: react + nextjs, typescript, tailwind.
- Existing routes/pages in `app/`.
- Existing components in `components`.
- State ownership, data-fetching lifecycle, forms and validation, styling tokens, accessibility conventions, and test setup already in the repo.
- Stage-specific context (constraints, unknowns, approvals) carried in from prior stages.

### AI Behavior Expected

- Restate the goal in concrete frontend terms.
- Inspect relevant files before asking questions the repo can already answer.
- Identify affected routes, components, hooks/composables, state and data boundaries, forms, styling tokens, and tests.
- Surface constraints, unknowns, and risky assumptions early — especially around accessibility (a11y), responsive behavior, performance, and adapter output.
- Ask only for decisions that cannot be discovered safely from the repo.

### AI Behavior Forbidden

- Combining Think and Plan when an approval checkpoint is required.
- Jumping straight to implementation.
- Replacing established component, styling, routing, or state patterns without a named reason.
- Generic lifecycle guidance that does not name specific frontend concerns (routing, components, state, data, styling, a11y, performance).
- Treating generic advice as sufficient when stack-specific guidance exists in your project's rule documentation.

### Output Expected

- Restated goal in concrete frontend terms.
- Inspected files and existing conventions.
- Known constraints.
- Missing context and open questions for the user.
- Initial risk areas (a11y, responsive, performance, adapter output).
- Recommended next step.

### Quality Bar

Think is complete when the AI can name the likely frontend files, conventions, risks, and unresolved decisions before any planning begins.

## Backend (`backend/`)

### Stage Goal

Inspect backend structure and operational constraints before recommending changes. Understand the requested change, the FastAPI + Pydantic + uv stack, existing project conventions, and the operational, data, and security risks involved before proposing work.

### Inputs Needed

- User goal and acceptance criteria.
- Existing routes/controllers, services, data models, migrations, auth boundaries, integrations, async jobs, logging, and tests.
- Your project's rule guidance for architecture, API, data, security, integrations, async work, observability, and testing.
- Runtime constraints around compatibility, data safety, security, rollout, and rollback.

### AI Behavior Expected

- Restate the goal in concrete backend terms.
- Inspect relevant files before asking questions the repo can answer.
- Identify likely API contract, data layer, auth/security, integration, async, observability, and test impact.
- Surface high-risk areas early — especially destructive migrations, public API changes, auth behavior, idempotency on external delivery, and third-party calls.
- Ask for clarification only when a decision cannot be discovered safely from the repo.

### AI Behavior Forbidden

- Jumping straight to implementation.
- Guessing framework, ORM, validation, auth, or test conventions without inspection.
- Expanding scope beyond the requested backend behavior.
- Treating API, data, or auth changes as low risk by default.
- Silent public API changes.

### Output Expected

- Restated goal in concrete backend terms.
- Inspected backend areas and current patterns.
- Known constraints and missing context.
- Initial risk areas (contracts, data, auth, integrations, async, observability).
- Open questions for the user.
- Recommended next lifecycle stage.

### Quality Bar

Think is complete when the AI can name the likely backend files, contracts, data/auth/integration risks, and unresolved decisions before planning.
