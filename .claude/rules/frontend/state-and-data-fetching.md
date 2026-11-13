---
description: Guide frontend state and data fetching choices.
paths:
  - "frontend/**"
---
# State And Data Fetching

Guide frontend state and data fetching choices.

Use this rule during the Think, Plan, Build, Review, and Test stages.

Before adding state, decide whether it is local UI state, shared client state, server state, URL state, or persisted state. Before changing data access, identify the owning API client, cache strategy, loading/error/empty states, and mutation invalidation behavior.

## AI Responsibilities

- Keep state local unless it is shared, persisted, or cross-route.
- Follow existing data fetching conventions.
- Model loading, empty, error, and success states.
- Avoid duplicated request logic.
- Define retry and invalidation behavior when relevant.

## AI Must Avoid

- Adding global state for isolated UI behavior.
- Swallowing request failures.
- Updating cached data without considering invalidation.

## Stack-Specific Guidance

For client-side fetching libraries, prefer existing query keys, cache invalidation patterns, and error display conventions.

### State management


- One store per domain; export selectors; avoid storing non-serializable objects unless intentional.

#### SSR / hydration

- Ensure server and client render **consistent initial state**; avoid reading `window` during first paint on server bundles.

#### Ownership rules

- Keep state local when only one component subtree needs it.
- Lift state only to the nearest common owner.
- Use URL/search params for shareable navigation or filter state.
- Use server-state tooling for cache, invalidation, and async data; do not duplicate it in client stores.
- Persist state only when the product behavior requires it.

### Data fetching


- **Query keys** are part of your API: colocate factory functions (`queryKeys.user(id)`).
- Set sensible `staleTime`; invalidate on mutations; prefer `prefetchQuery` for perceived performance.

#### Pagination

- Prefer **cursor-based** APIs when available; show loading rows or skeletons, not spinners only.

#### Auth headers

- Attach tokens in **one** place (interceptor / link / fetch wrapper), not per call site.

#### UI state contract

- Every async view needs loading, error, empty, and success states.
- Mutations should define optimistic behavior, disabled states, retries, and post-success cache updates where relevant.
- Avoid leaking transport errors directly to users; map them to useful UI copy.

## Acceptance Criteria

- State owner is named.
- Data lifecycle states are handled.
- Failure mode is visible to the user or caller.
- Tests or manual checks cover success and failure paths.
- Data owner, cache key/invalidation, and UI states are named.
- Auth/session behavior is preserved.
