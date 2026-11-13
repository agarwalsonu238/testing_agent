---
description: Guide external service integration and async job reliability.
paths:
  - "backend/**"
---
# Integrations And Async Patterns

Guide external service integration and async job reliability.

Use this rule during the Plan, Build, Review, and Test stages.

Any code that calls a third-party API (e.g., Stripe, SendGrid, Twilio, AWS) must be cleanly abstracted, and any non-trivial work that does not need to block the HTTP request-response cycle should be moved to a background queue.

## AI Responsibilities

- Identify external failure modes.
- Define timeout, retry, and backoff expectations.
- Make idempotency explicit for webhooks and jobs.
- Preserve consistent logging and observability.
- Add tests or manual checks for failure paths.
- Persist provider identifiers and idempotency keys when needed for reconciliation.

## AI Must Avoid

- Direct provider calls from controllers/handlers or unrelated services.
- Assuming external calls always succeed.
- Retrying non-idempotent operations blindly.
- Dropping failed jobs without visibility.
- Hiding provider-specific assumptions.
- Logging webhook secrets, access tokens, or full provider payloads by default.
- Fire-and-forget work with no retry, dead-letter queue (DLQ), or log visibility.
- Large or sensitive payloads in queues.
- Cron jobs that run once per app instance in horizontally scaled deployments.

## Stack-Specific Guidance

### External Integrations: Wrapper Service Pattern
- Each third-party API gets a client module in `app/integrations/<provider>.py` wrapping a shared
  `httpx.AsyncClient` (created in `lifespan`). Routes and services never call `httpx` directly.

### External Integrations: Error Handling
- Translate provider errors into domain exceptions; never bubble raw `httpx` errors to the API layer.

### External Integrations: Retries & Timeouts
- Always set explicit timeouts (`httpx.Timeout(10.0)`). Retry only idempotent calls, with backoff and a cap.

### External Integrations: Webhooks
- Verify signatures before parsing the body; respond fast (2xx) and push heavy work to a background job.
- Make handlers idempotent using the provider's event id.

### Async: Background Work
- `BackgroundTasks` is acceptable only for short, best-effort work (e.g. sending a notification).
- Durable or retryable jobs need a real queue/worker; adding one (e.g. arq, Celery) requires approval in Plan.

### Async: Cron & Scheduled Tasks
- Scheduled jobs are standalone entry points (`uv run python -m app.jobs.<name>`), not loops inside the API process.

## Acceptance Criteria

- External contract is named.
- Timeout/retry/failure behavior is documented.
- Idempotency is addressed where relevant.
- Webhook verification and duplicate-delivery handling are checked where relevant.
- Async contract, retry policy, and DLQ behavior are observable.
- Tests or manual checks cover failure paths.
