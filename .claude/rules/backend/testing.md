---
description: Guide validation choices for the FastAPI backend (`backend/`).
paths:
  - "backend/**"
---
# Backend Testing

Guide validation choices for the FastAPI backend (`backend/`).

Use this rule during the Review and Test stages.

This project uses **pytest** for testing. Choose validation proportional to risk and cover success, validation failure, auth failure, and integration failure paths where relevant.

## AI Responsibilities

- Choose validation proportional to risk.
- Cover success, validation failure, auth failure, and integration failure paths where relevant.
- Include migration and contract checks for schema/API changes.
- Plan tests before implementation for non-trivial backend changes.
- Use targeted checks for narrow changes, then broaden when public APIs, data, auth, integrations, async behavior, or generated output changes.
- Include manual QA when automation does not cover migrations, provider behavior, deployment order, or adapter output.
- State untested areas clearly.

## AI Must Avoid

- Treating unit tests as enough for public contract changes.
- Unit-only validation for public contract, migration, auth, or integration changes.
- Skipping failure-path tests for integrations.
- Skipping validation failure, auth denial, not-found, provider failure, retry, and duplicate-delivery paths when relevant.
- Tests that assert implementation details instead of observable behavior.
- Claiming smoke or adapter/generated-output checks passed without running or inspecting them.

## Stack-Specific Guidance

Tests use **pytest** + **pytest-asyncio** (`asyncio_mode = "auto"`) + **httpx**. Run: `cd backend && uv run pytest`.

### Unit Tests
- Services and pure helpers get direct unit tests in `tests/unit/` (no HTTP, no app).
- Name tests `test_<behavior>_<condition>` and cover success **and** failure paths.

### API (Integration) Tests
- Use the `client` fixture from `tests/conftest.py` (`httpx.AsyncClient` + `ASGITransport` over `create_app()`).
- Assert status code **and** response body shape for every endpoint, including 4xx cases.
- Override dependencies with `app.dependency_overrides[...]`, not monkeypatching module globals.

### Mocking Conventions
- Mock at the integration boundary (`app/integrations/*`), never the code under test.
- Use `respx` for outbound `httpx` calls if/when integrations exist (add it as a dev dependency with approval).

### Docstrings
- Public service functions get a short docstring describing behavior and raised domain errors.

## Acceptance Criteria

- Relevant automated or manual checks are listed.
- Contract and migration risks have validation.
- Failure paths are covered where material.
- Untested areas are explicit.
- Build, unit/integration/E2E, migration, smoke, and manual checks are recorded when relevant.
