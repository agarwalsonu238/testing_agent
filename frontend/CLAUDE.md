@AGENTS.md

# Frontend — Next.js

Next.js 16 (App Router, `src/` dir, TypeScript strict) · Tailwind CSS v4 · shadcn/ui (`base-nova`) · Vitest + Testing Library.
Rules: `../.claude/rules/frontend/` (auto-loaded for `frontend/**`). Lifecycle: `../.claude/skills/`.

## Layout

| Area | Path | Notes |
|---|---|---|
| Routes / layouts | `src/app/` | App Router. `cacheComponents` is on — read the Next docs in `node_modules/next/dist/docs/` before using caching/dynamic APIs |
| UI primitives | `src/components/ui/` | shadcn-generated; add with `npx shadcn@latest add <name>`, don't hand-edit unless needed |
| Feature components | `src/components/` | Co-locate tests as `*.test.tsx` |
| API client | `src/lib/api.ts` | All backend calls go through `apiFetch`; add typed helpers here |
| Utils | `src/lib/utils.ts` | `cn()` etc. |

## Stack policy

Installed: Next.js, React 19, Tailwind v4, shadcn/ui, lucide-react, Vitest, Testing Library.
Approved when needed (ask before adding): Zustand (client state), TanStack Query (server state),
React Hook Form + Zod (forms), Storybook, Playwright (E2E). Anything else needs explicit approval.

## Env

- `NEXT_PUBLIC_BACKEND_URL` — browser-facing backend URL, inlined at build time (Docker build arg).
- Copy `.env.example` → `.env.local`. Never commit real env files.
- The local shell may export `NODE_ENV=production`; `.npmrc` (`include=dev`) and `vitest.config.mts` (`NODE_ENV=test`) compensate.

## Quality Gates

```bash
npm run lint && npm run typecheck && npm test && npm run build
```
