---
description: Guide architecture decisions in the Next.js frontend (`frontend/`).
paths:
  - "frontend/**"
---
# Architecture

Guide architecture decisions in the Next.js frontend (`frontend/`).

Use this rule during the Think, Plan, Build, and Review stages.

Before changing architecture, identify affected routes/pages, layout boundaries, reusable components, state ownership, data-fetching boundaries, and test coverage. Prefer local changes over broad restructuring.

## AI Responsibilities

- Inspect current architecture before proposing new files.
- Keep route, layout, component, state, and data boundaries explicit.
- Prefer local changes over broad restructuring.
- Identify when a shared abstraction is justified by repeated behavior.

## AI Must Avoid

- Creating new architecture layers for one-off use cases.
- Moving state globally before it is shared or persisted.
- Changing route structure without naming user-facing impact.

## Stack-Specific Guidance

For React-style projects, separate route/page orchestration from reusable components, keep data-loading states close to the consuming view unless shared, and preserve existing framework conventions.

### Directory layout

- Prefer **App Router** (`app/`) for routes, layouts, and server components where applicable.
- Shared UI in `components/`; feature code under `app/(segments)/` or `src/features/` if you use a src layout.

Primary paths in this project (tune to match your repo):

- **Components:** `components`
- **Routes / pages:** `app/`
- **Global state (if any):** `src/stores`

- Prefer function components; colocate small presentational pieces next to features.
- Extract reusable logic into custom hooks (`useThing`) in `src/hooks/` or feature folders.

### Layering

1. **Presentation** — dumb UI, minimal logic, props/slots in, events out.
2. **Application** — hooks/composables/services orchestrating user flows.
3. **Data** — API clients, query hooks, DTO mappers (keep framework-agnostic where possible).

### Decision rules

- Route/page files orchestrate page-level composition; reusable components stay focused on UI behavior.
- Shared abstractions need repeated behavior or a clear ownership boundary, not a single call site.
- Global state is justified only when state is shared across routes/components, persisted, or required by app-level workflows.
- Data-loading, empty, error, and permission states should be named in the plan before implementation.

### Barrel exports

- Use `index.ts` sparingly at **feature boundaries**; avoid mega-barrels that harm tree-shaking.

### Co-location

- Prefer tests and styles next to the component when the team does so consistently.

### Commands

**Build:** `npm run build`  
**Typecheck:** `npm run typecheck`  
**Dev:** `next dev`  
**Lint:** `npm run lint`

## Acceptance Criteria

- Architecture changes name affected routes/components.
- State and data ownership are explained.
- Tests or manual checks cover key user flows.
