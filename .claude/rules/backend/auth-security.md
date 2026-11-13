---
description: Guide authentication, authorization, validation, and sensitive-data handling.
paths:
  - "backend/**"
---
# Auth And Security

Guide authentication, authorization, validation, and sensitive-data handling.

Use this rule during the Think, Plan, Build, Review, and Test stages.

Before changing auth or sensitive-data behavior, identify caller permissions, resource ownership, input validation patterns, sensitive-data flow, and the allowed/denied test cases.

## AI Responsibilities

- Identify who can call the changed behavior.
- Check authentication and authorization separately — authentication answers "who is this" and authorization answers "are they allowed to touch this specific resource."
- Validate untrusted input.
- Avoid logging secrets or sensitive payloads.
- Consider abuse cases and privilege boundaries.
- Enforce both the caller's permission and resource ownership (are they allowed to touch this specific record ID?).

## AI Must Avoid

- Assuming authentication implies authorization.
- Returning sensitive data by default.
- Adding bypasses for convenience.
- Changing security-sensitive behavior without tests or explicit review.
- Logging PII, passwords, tokens, raw credentials, or sensitive financial details.

## Stack-Specific Guidance

Use existing middleware, guards, policies, or permission helpers rather than inventing parallel authorization logic.

- Validate JWT signatures on all protected routes.
- Extract user IDs from the verified token payload, not from request bodies.

## Acceptance Criteria

- Authn/authz impact is named, checked separately.
- Input validation is defined.
- Sensitive data handling is checked.
- Allowed and denied cases are tested or manually checked.
