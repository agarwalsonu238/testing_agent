# frontend

Next.js (App Router, TypeScript) + Tailwind CSS v4 + shadcn/ui.

```bash
cp .env.example .env.local     # NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
npm install
npm run dev                    # http://localhost:3000
npm run lint && npm run typecheck && npm run build
```

- API client: `src/lib/api.ts` (`apiFetch`, typed helpers under `/api/v1`)
- UI primitives: `src/components/ui/` (add more with `npx shadcn@latest add <component>`)
