---
description: Guide backend architecture and API contract decisions in the FastAPI backend (`backend/`).
paths:
  - "backend/**"
---
# Backend Architecture And API

Guide backend architecture and API contract decisions in the FastAPI backend (`backend/`).

Use this rule during the Think, Plan, Build, and Review stages.

Before changing backend structure or an endpoint, identify affected routes/controllers, services, repositories, data models, auth boundaries, request/response shape, status codes, validation, error behavior, versioning impact, integrations, jobs, and tests. Prefer local changes over broad restructuring.

## AI Responsibilities

- Inspect current API patterns before adding endpoints.
- Preserve public contracts unless a plan explicitly changes them.
- Define request validation, response shape, status codes, and error cases.
- Identify compatibility and versioning risks.
- Keep transport, business logic, persistence, and external integration concerns separated when the repo already separates them.

## AI Must Avoid

- Silent response shape or status-code changes.
- Mixing transport, business, and persistence logic when the project separates them.
- Adding endpoints without validation and error behavior.
- Creating new architecture layers for one-off work.
- Bypassing dependency injection, config, logging, or error handling conventions.

## Stack-Specific Guidance

This project uses **FastAPI** (Python 3.12, Pydantic v2), managed with **uv**. Package root: `backend/src/app/`.

### App Layout
- `app/main.py` holds `create_app()` only: settings, middleware, router mounting. Keep it minimal.
- `app/api/router.py` aggregates feature routers; all public routes live under `settings.api_v1_prefix` (`/api/v1`).
- One module per resource in `app/api/routes/<resource>.py`, each exposing `router = APIRouter(tags=["<resource>"])`.
- When business logic appears, add `app/services/<resource>.py` (pure logic, no `Request`/`Response`), and
  `app/repositories/<resource>.py` once a database exists. Route handlers never talk to the DB driver directly.

### Layers
- **Routes:** parse/validate input via Pydantic models and `Depends(...)`, call a service, return a response model. No business logic.
- **Services:** plain Python functions/classes. They do not import FastAPI.
- **Repositories:** all persistence calls. Injected into services via `Depends` providers.
- **Dependencies:** shared concerns (settings, current user, DB session) are `Depends` providers in `app/api/deps.py`.

### Request / Response Models
- Every endpoint declares `response_model=` (or a typed return) and uses Pydantic models for bodies — never raw `dict`.
- Keep API schemas in `app/schemas/<resource>.py`; do not expose ORM models directly.
- Use `Field(...)` constraints (`min_length`, `ge`, regex `pattern`) instead of manual checks in handlers.
- Declare non-200 success codes explicitly (`status_code=status.HTTP_201_CREATED`).

### Async
- Handlers are `async def`. Never call blocking I/O (requests, time.sleep, sync DB drivers) inside them;
  use async clients (`httpx.AsyncClient`) or `run_in_threadpool` for unavoidable sync work.

### Pagination
- Prefer cursor-based pagination for high-volume endpoints; offset/limit is fine for small admin lists.
- Wrap paginated responses in a standard envelope model: `{"items": [...], "next_cursor": str | None}`.

### CORS & Security Headers
- CORS is configured once in `create_app()` from `settings.cors_origins`. Never use `allow_origins=["*"]` with credentials.

### API Versioning
- Breaking changes go to a new prefix (`/api/v2`) with a new router; `/api/v1` keeps its contract.

### Lifespan / Shutdown
- Create and close shared clients (HTTP, DB pools) in a FastAPI `lifespan` context manager, not at import time.

## Acceptance Criteria

- Affected routes/controllers/services/repositories are named.
- API change names request and response shape.
- Error cases and status codes are defined.
- Compatibility risk is named.
- Tests cover success and failure paths.
