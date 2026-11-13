# Plan: <title>

- **Date:** YYYY-MM-DD
- **Status:** draft | approved | done
- **Sides:** frontend | backend | both
- **Ticket / request:** <link or one-line summary>

## Goal

<What changes for the user, in 1–3 sentences. Acceptance criteria as a checklist.>

- [ ] …

## Out of scope

- …

## Approach

<Smallest path that matches existing conventions.>

## File impact map

| File | Change |
|---|---|
| `backend/src/app/api/routes/…` | add / modify / delete |
| `frontend/src/…` | … |

## API contract (if both sides)

| Method | Path | Request | Response | Errors |
|---|---|---|---|---|
| GET | `/api/v1/…` | … | … | 404, 422 |

## Data / state delta

<Models, migrations, client state ownership. "None" if none.>

## Risks & tradeoffs

- …

## Approval needed for

<New deps, contract changes, migrations, auth changes. "None" if none.>

## Test plan

- Backend: `uv run pytest` — cases: …
- Frontend: `npm test` — cases: …
- Manual: …
