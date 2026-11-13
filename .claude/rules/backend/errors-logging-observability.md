---
description: Guide backend error handling, logging, and operational visibility.
paths:
  - "backend/**"
---
# Errors, Logging, And Observability

Guide backend error handling, logging, and operational visibility.

Use this rule during the Build, Review, Test, and Ship stages.

Before changing error handling, logging, or observability behavior, identify public error shape, log fields, retryable vs. non-retryable failures, and failure-path tests.

## AI Responsibilities

- Return consistent errors to callers.
- Log useful operational context without secrets.
- Preserve traceability across request, integration, and job boundaries.
- Identify retryable and non-retryable failures.

## AI Must Avoid

- Swallowing errors without visibility or remediation path.
- Logging sensitive tokens or full credentials.
- Returning internal implementation details, stack traces, SQL errors, provider internals, or config values to public clients.
- Adding noisy logs without operational value.

## Stack-Specific Guidance

### Error Handling
- Raise `HTTPException(status_code=..., detail=...)` from routes for expected client errors (404, 409, 422).
- Services raise domain exceptions (e.g. `NotFoundError`) defined in `app/core/errors.py`; map them to HTTP
  responses with `app.exception_handler(...)` in `create_app()` — services never raise `HTTPException`.
- Never leak stack traces, SQL, or internal IDs in `detail`. Unexpected errors return a generic 500.
- Let Pydantic produce 422 validation errors; don't re-validate manually.

### Logging & Observability
- Use the stdlib `logging` module via `logger = logging.getLogger(__name__)`; no `print()`.
- Log with context (request id, resource id) and never log secrets, tokens, or full request bodies with PII.
- Use `logger.exception(...)` inside `except` blocks so tracebacks are captured.

## Acceptance Criteria

- Error shape is consistent.
- Logs include useful context and exclude secrets.
- Failure modes are testable or manually checkable.
- Observability changes preserve request correlation.
- Known limitations are documented for release.
