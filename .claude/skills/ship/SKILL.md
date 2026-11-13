---
name: ship
description: "Ship stage of the lifecycle (Think → Plan → Build → Review → Test → Ship → Reflect) for this Next.js + FastAPI monorepo: prepare work for release or handoff. Use when the user invokes /ship or a non-trivial change reaches this stage."
---

# Ship

This repo has two apps. Decide which side(s) the change touches, then apply the matching section(s).
If both are touched, apply both, and also check the **API contract** between them
(`backend/src/app/api/` ↔ `frontend/src/lib/api.ts`): request/response shapes, status codes, and `/api/v1` paths must stay in sync.

- Frontend rules: `.claude/rules/frontend/` · context: `frontend/CLAUDE.md`
- Backend rules: `.claude/rules/backend/` · context: `backend/CLAUDE.md`

## Frontend (`frontend/`)

### Stage Goal

Summarize changes, validation evidence, and rollback path for approved frontend work. Do not ship without a visible test result.

### Inputs Needed

- Final diff or artifact list.
- Test output and manual QA notes.
- Known limitations.
- Rollback considerations.
- Generated output review when lifecycle or rule templates changed.

### AI Behavior Expected

- Summarize user-visible behavior and changed files.
- Provide validation notes with exact commands and results.
- Draft release notes when behavior or generated output changes.
- Call out breaking changes or output-path changes for any adapter target.
- Identify rollback steps when relevant.

### AI Behavior Forbidden

- Claiming release readiness while blockers remain.
- Omitting known limitations or skipped checks.
- Skipping adapter review for generated-output changes.

### Output Expected

- Change summary.
- Validation notes (commands and results).
- Release notes draft.
- Breaking-change callout.
- Rollback notes.

### Quality Bar

Ship is complete when reviewers can see what changed, how it was validated, what risks remain, and how to recover if needed.

## Backend (`backend/`)

### Stage Goal

Summarize changes, validation, release notes, breaking changes, and rollback concerns for approved backend work. Do not ship without a visible test result.

### Inputs Needed

- Final diff or artifact list.
- Test output.
- Known limitations.
- Adapter output review when generated files changed.

### AI Behavior Expected

- Summarize behavior delivered.
- Summarize validation commands and results.
- Call out public API changes, data/migration changes, auth/security changes, output path changes, and breaking changes.
- Draft release notes when relevant.
- Identify rollback or remediation steps (for example, `db migrate:down` plus reverting route registration for an endpoint change).
### AI Behavior Forbidden

- Claiming release readiness while blockers remain.
- Omitting known limitations.
- Skipping adapter review for generated-output changes.

### Output Expected

- Change summary.
- Validation notes (commands and results).
- Release notes draft.
- Breaking-change and compatibility callout.
- Rollback / remediation notes.

### Quality Bar

Ship is complete when reviewers can see what changed, how it was validated, what risks remain, and how to recover if needed.
