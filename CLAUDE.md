# testing_agent

Monorepo with two independent apps:

| App | Path | Stack | Context |
|---|---|---|---|
| Frontend | `frontend/` | Next.js 16 (App Router, TS) · Tailwind v4 · shadcn/ui · Vitest | `frontend/CLAUDE.md` |
| Backend | `backend/` | FastAPI · Pydantic v2 · Python 3.12 · uv · pytest | `backend/CLAUDE.md` |

The frontend talks to the backend over HTTP at `NEXT_PUBLIC_BACKEND_URL` + `/api/v1`
(`frontend/src/lib/api.ts` ↔ `backend/src/app/api/`). Keep both sides in sync when a contract changes.

## Core Principles

1. **Read first, write second.** Inspect existing patterns in the side you're changing before adding new ones.
2. **Stay on one side unless the task crosses the contract.** Don't refactor the other app opportunistically.
3. **Plan before building** anything non-trivial (see Lifecycle). Plans are saved under `docs/plans/`.
4. **No new dependencies or architecture layers** (DB, queue, state library, auth provider) without explicit approval.
5. **Evidence over claims.** Never say tests/lint passed without running them.

## Lifecycle (skills)

Think → Plan → Build → Review → Test → Ship → Reflect — `.claude/skills/<stage>/SKILL.md`, invoke as `/think`, `/plan`, …
Each skill has a Frontend and a Backend section; apply the one(s) matching the files you touch.
Trivial changes (typos, copy, one-line config) can skip straight to Build + Test.

## Rules

Path-scoped rules load automatically: `.claude/rules/frontend/*` for `frontend/**`, `.claude/rules/backend/*` for `backend/**`.

## Quality Gates

```bash
# frontend/
npm run lint && npm run typecheck && npm test && npm run build
# backend/
uv run ruff format --check . && uv run ruff check . && uv run mypy src tests && uv run pytest
```

## Run

- Both apps, hot reload: `./run-local-dev.sh` (FE http://localhost:3000, BE http://localhost:8000/docs)
- Containers: `docker compose up --build`
