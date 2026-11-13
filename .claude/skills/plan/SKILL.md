---
name: plan
description: "Plan stage of the lifecycle (Think → Plan → Build → Review → Test → Ship → Reflect) for this Next.js + FastAPI monorepo: produce a concrete implementation plan before coding. Use when the user invokes /plan or a non-trivial change reaches this stage."
---

# Plan

This repo has two apps. Decide which side(s) the change touches, then apply the matching section(s).
If both are touched, apply both, and also check the **API contract** between them
(`backend/src/app/api/` ↔ `frontend/src/lib/api.ts`): request/response shapes, status codes, and `/api/v1` paths must stay in sync.

- Frontend rules: `.claude/rules/frontend/` · context: `frontend/CLAUDE.md`
- Backend rules: `.claude/rules/backend/` · context: `backend/CLAUDE.md`

## Plan Artifact

Write the approved plan to a file so it survives the conversation:

- If agentsmyth is installed (`workflow/router.md` exists), follow its plan phase and write the artifact it
  specifies under `workflow/artifacts/plans/`.
- Otherwise write `docs/plans/YYYY-MM-DD-<short-slug>.md` using `docs/plans/_template.md`.

Stop after writing the plan and ask for approval. Do not start Build in the same step.

## Frontend (`frontend/`)

### Stage Goal

Produce a scoped frontend implementation plan before editing files. List every file that will change, the state or data model delta, test cases to add or update, and risks. Do not combine Plan and Build.

### Inputs Needed

- Output from Think (restated goal, inspected areas, constraints, open questions).
- Existing routes/pages, components, state/data patterns, styling approach, and tests.
- Acceptance criteria and out-of-scope items.
- Compatibility, accessibility, performance, and release constraints.

### AI Behavior Expected

- Name affected routes, components, hooks/composables/services, styles, and tests.
- Define state ownership and server-state/data-fetching boundaries explicitly.
- Identify accessibility, responsive, loading, error, empty, and performance concerns per affected surface.
- Choose the smallest implementation path that matches existing conventions.
- Define validation commands and manual checks proportional to risk.
- Call out items that require user approval before Build (new dependencies, contract changes, behavior changes, output path changes).

### AI Behavior Forbidden

- Planning vague work like "clean up UI" or "make it scalable".
- Introducing new libraries without explicit approval.
- Moving state globally before it is shared, persisted, or required by the workflow.
- Hiding unresolved user-facing behavior decisions.
- Combining Plan and Build in a single step when approval is needed.

### Output Expected

- Proposed approach.
- File impact map (files to change, files to add, files to delete).
- State / data model delta.
- Scope boundaries (in and out).
- Risks and tradeoffs.
- Test strategy (unit, component, integration, manual).
- Open questions, if any.

### Quality Bar

Plan is complete when another engineer could implement the frontend change without making major product, accessibility, or architecture decisions.

## Backend (`backend/`)

### Stage Goal

List affected API contracts, data models, migrations, auth boundaries, integrations, jobs, tests, and risks before any code changes. Do not combine Plan and Build.

### Inputs Needed

- Output from Think (restated goal, inspected areas, constraints, open questions).
- Relevant source files and tests.
- Existing FastAPI, Pydantic, settings, auth, logging, and pytest conventions.
- Acceptance criteria and rollout constraints.

### AI Behavior Expected

- Name affected APIs, controllers/routes, services, repositories, schemas/entities, migrations, integrations, jobs, and tests.
- Define request/response shape, status codes, validation, error behavior, and compatibility impact for API changes.
- Identify data model or migration impact, including destructive operations and rollback or remediation needs.
- Identify authentication (authn) and authorization (authz) impact separately.
- Define automated and manual validation proportional to risk (unit, integration, contract, migration, smoke, manual).
- Ask approval before public contract changes, destructive migrations, auth behavior changes, new dependencies, or output path changes.

### AI Behavior Forbidden

- Planning vague work such as "clean up backend code."
- Hiding unresolved API, data, auth, or integration decisions.
- Including unrelated refactors.
- Treating tests or migration checks as optional when behavior changes.
- Destructive migration changes without rollback notes.

### Output Expected

- Proposed approach.
- File or subsystem impact map.
- State / data model delta and migration plan.
- Scope boundaries (in and out).
- API / data / auth / integration risks and tradeoffs.
- Test and smoke strategy.
- Open questions or approval points.

### Quality Bar

Plan is complete when another engineer could implement the backend change without making major product, contract, data, or security decisions.
