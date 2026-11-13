---
name: reflect
description: "Reflect stage of the lifecycle (Think → Plan → Build → Review → Test → Ship → Reflect) for this Next.js + FastAPI monorepo: capture delivery lessons and template gaps. Use when the user invokes /reflect or a non-trivial change reaches this stage."
---

# Reflect

This repo has two apps. Decide which side(s) the change touches, then apply the matching section(s).
If both are touched, apply both, and also check the **API contract** between them
(`backend/src/app/api/` ↔ `frontend/src/lib/api.ts`): request/response shapes, status codes, and `/api/v1` paths must stay in sync.

- Frontend rules: `.claude/rules/frontend/` · context: `frontend/CLAUDE.md`
- Backend rules: `.claude/rules/backend/` · context: `backend/CLAUDE.md`

## Frontend (`frontend/`)

### Stage Goal

Record what the plan missed, what surprised the reviewer, and what should be added to the risk template for this type of change so future frontend work and generated templates improve.

### Inputs Needed

- Completed work summary.
- Test and review results.
- User or reviewer feedback.
- Repeated friction, missing rule guidance, or unclear generated instructions.

### AI Behavior Expected

- Record what worked.
- Record what failed or slowed the work.
- Identify missing frontend template guidance (routing, components, state, data, styling, a11y, performance, testing).
- Create follow-up tasks or research notes with concrete next actions.
- Propose updates to your project's rule or lifecycle guidance when repeated issues appear.

### AI Behavior Forbidden

- Turning reflection into vague praise.
- Recording lessons without actions.
- Reopening settled decisions without new evidence.
- Expanding scope into unrelated domains.

### Output Expected

- What worked.
- What failed or slowed delivery.
- Template gaps.
- Follow-up tasks.
- Rejected or deferred ideas, if any.

### Quality Bar

Reflect is complete when future work has a concrete improvement path or a recorded reason not to revisit a decision.

## Backend (`backend/`)

### Stage Goal

Record template gaps and follow-up tasks so future rule guidance, adapters, and release workflows improve.

### Inputs Needed

- Completed work summary.
- Test results.
- Review feedback.
- User, release, or operations feedback.
- Template gaps or repeated friction.

### AI Behavior Expected

- Record what worked and what slowed the work.
- Identify missing API, data, auth, migration, integration, async, observability, testing, or adapter guidance.
- Create follow-up tasks with owners or next actions when possible.
- Record rejected or deferred ideas when a tempting approach should not be repeated.
- Propose additions to the risk template when a recurring issue surfaces (for example, retry-policy checklist for backend integration work).

### AI Behavior Forbidden

- Turning reflection into vague praise.
- Recording lessons without actions.
- Reopening settled decisions without new evidence.
- Expanding scope into unrelated template tracks.

### Output Expected

- What worked.
- What failed or slowed delivery.
- Backend template gaps.
- Follow-up tasks.
- Rejected or deferred ideas, if any.

### Quality Bar

Reflect is complete when there is a concrete improvement path or a recorded reason not to revisit a decision.
