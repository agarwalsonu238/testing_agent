# Backend — FastAPI

FastAPI · Pydantic v2 / pydantic-settings · Python 3.12 · uv · pytest + httpx · ruff · mypy (strict).
Rules: `../.claude/rules/backend/` (auto-loaded for `backend/**`). Lifecycle: `../.claude/skills/`.

## Layout

| Area | Path | Notes |
|---|---|---|
| App factory | `src/app/main.py` | `create_app()`: settings, CORS, router mount. Keep minimal |
| Settings | `src/app/core/config.py` | Only place that reads env. Add every new field to `.env.example` |
| Router | `src/app/api/router.py` | Mounted at `/api/v1` |
| Routes | `src/app/api/routes/<resource>.py` | Thin: validate → call service → return response model |
| Services / schemas / repositories | `src/app/services/`, `src/app/schemas/`, `src/app/repositories/` | Create when first needed |
| Tests | `tests/` | `client` fixture = `httpx.AsyncClient` over `create_app()` |

## Stack policy

No database, auth, queue or external integrations yet. Adding any of them is a Plan-stage decision needing approval
(defaults when approved: SQLAlchemy 2 async + Alembic + PostgreSQL; httpx for outbound calls).
Add dependencies with `uv add <pkg>` / `uv add --dev <pkg>` so `uv.lock` stays in sync — never `pip install`.

## Commands

```bash
uv sync                                    # install
uv run uvicorn app.main:app --reload       # http://localhost:8000/docs
uv run ruff format --check . && uv run ruff check . && uv run mypy src tests && uv run pytest   # quality gates
```
