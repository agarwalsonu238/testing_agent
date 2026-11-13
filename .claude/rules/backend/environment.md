---
description: Guide environment variable usage, runtime configuration, and secrets management in the FastAPI backend (`backend/`).
paths:
  - "backend/**"
---
# Environment And Configuration

Guide environment variable usage, runtime configuration, and secrets management in the FastAPI backend (`backend/`).

Use this rule during the Plan, Build, and Review stages.

All configuration values must flow through environment variables (12-Factor App methodology). Never commit `.env` files or hardcode environment-specific values in source.

## AI Responsibilities

- Never hardcode environment-specific values (database URLs, API keys, signing secrets) in source files.
- Add new variables to `.env.example` with a placeholder value when introducing them.
- Keep secrets server-side only; never log, serialize, or return them in API responses.
- Use the project's existing config loading pattern rather than introducing a new one.
- Validate required environment variables at startup and fail fast with a clear message if any are missing.

## AI Must Avoid

- Committing real secrets or credentials to source control.
- Using different variable names across environments for the same value.
- Accessing environment variables deep inside domain logic; prefer injecting config at the application boundary.
- Silently defaulting to insecure fallback values when an env var is missing.

## Stack-Specific Guidance

### Environment Variables (`.env`)
- All config is read through `app.core.config.Settings` (pydantic-settings). Never call `os.environ` / `os.getenv` elsewhere.
- Every new setting gets a typed field with a safe default (or no default if required) **and** an entry in `backend/.env.example`.
- Access settings via `get_settings()` (cached) or a `Depends(get_settings)` provider so tests can override it.
- `.env` is git-ignored; `.env.example` is committed and contains no real secrets.
- List values are JSON in env, e.g. `CORS_ORIGINS=["http://localhost:3000"]`.

### Configuration Management
- Use `Literal[...]` / enums for constrained values (e.g. `environment`) so bad config fails at startup.
- Secrets use `SecretStr` and are never logged or returned in responses.

### Feature Flags
- Simple flags are boolean `Settings` fields; do not add a flag service without approval.

### Containerization (Docker)
- `backend/Dockerfile` installs with `uv sync --frozen --no-dev`; keep `uv.lock` committed and in sync (`uv lock`).
- Runtime config comes from env (`docker-compose.yml` / deployment), never baked into the image.

## Acceptance Criteria

- All new environment variables are documented in `.env.example`.
- No secrets appear in committed source files or logs.
- Missing required env vars cause a startup error, not a silent runtime failure.
