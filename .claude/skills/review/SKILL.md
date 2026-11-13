---
name: review
description: "Review stage of the lifecycle (Think → Plan → Build → Review → Test → Ship → Reflect) for this Next.js + FastAPI monorepo: self-review changes before presenting them. Use when the user invokes /review or a non-trivial change reaches this stage."
---

# Review

This repo has two apps. Decide which side(s) the change touches, then apply the matching section(s).
If both are touched, apply both, and also check the **API contract** between them
(`backend/src/app/api/` ↔ `frontend/src/lib/api.ts`): request/response shapes, status codes, and `/api/v1` paths must stay in sync.

- Frontend rules: `.claude/rules/frontend/` · context: `frontend/CLAUDE.md`
- Backend rules: `.claude/rules/backend/` · context: `backend/CLAUDE.md`

## Frontend (`frontend/`)

### Stage Goal

Self-review frontend changes for correctness, accessibility (a11y), performance, styling consistency, maintainability, and adapter output alignment. Flag regressions.

### Inputs Needed

- Changed files and diff.
- Original goal and acceptance criteria.
- Your project's rule guidance for routing, components, styling, state, data fetching, forms, and testing.
- Test output or validation notes.
- Generated adapter output when templates or lifecycle/rule content changed.

### AI Behavior Expected

- Check behavior against the original goal and user flow.
- Review edge cases: loading, error, empty, disabled, auth/session, and navigation states.
- Review accessibility: labels, roles, focus order, keyboard path, color contrast, motion, and live regions for dynamic content.
- Review performance: unnecessary re-renders, bundle impact, image/media handling, expensive effects, and observer/listener cleanup.
- Review maintainability: naming, file placement, duplication, and consistency with project patterns.
- Review adapter output consistency when generated instructions changed — confirm the per-adapter files render as expected.

### AI Behavior Forbidden

- Reporting only what changed.
- Ignoring failing, skipped, or missing tests.
- Treating style preference as correctness.
- Marking generated templates ready without checking adapter visibility.

### Output Expected

- Findings ordered by severity.
- Test gaps or residual risk.
- Clear ready / not-ready judgment.

### Quality Bar

Review is complete when meaningful frontend risks (correctness, a11y, performance, styling, adapter output) have been checked and known gaps are explicit.

## Backend (`backend/`)

### Stage Goal

Check correctness, security, data integrity, observability, integration failure modes, and adapter output before presenting backend changes. Apply extra attention to API contracts, migration safety, authn/authz, and idempotency.

### Inputs Needed

- Changed files or diff.
- Original goal and acceptance criteria.
- Test output or validation notes.
- Your project's rule guidance for architecture, API, data, security, integrations, async, and observability.
- Generated adapter output, if lifecycle, rule, or other instruction templates changed.

### AI Behavior Expected

- Check correctness against the original backend goal.
- Review request/response contracts, validation, status codes, and error shape.
- Review data integrity, migration safety, rollback/remediation, and deployment compatibility.
- Review authentication and authorization, sensitive-data handling, logging, and observability.
- Review external integration timeouts, retries, idempotency, and failure modes.
- Identify missing tests, manual checks, and residual risk.
- Review adapter output consistency when lifecycle, rule, or other generated instruction files change.

### AI Behavior Forbidden

- Reporting only what changed.
- Ignoring skipped or failing tests.
- Treating style preference as a correctness issue.
- Marking API, data, auth, or adapter changes ready without checking the quality bar.

### Output Expected

- Findings ordered by severity.
- Missing tests or manual checks.
- Residual risk.
- Ready / not-ready judgment when applicable.

### Quality Bar

Review is complete when backend correctness, safety, contract, data, failure-mode, and adapter risks have been checked and known gaps are explicit.
