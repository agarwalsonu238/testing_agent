# testing_agent

Internal local agent toolkit: Playwright tests and an exploratory Claude agent.

```
frontend/   Next.js 16 + Tailwind v4 + shadcn/ui (TypeScript)
backend/    FastAPI + Pydantic v2 (Python 3.12, uv)
.claude/    Claude Code rules (per app) + lifecycle skills (/think … /reflect)
docs/plans/ saved implementation plans
```

## Prerequisites

Node.js 22+, [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you), Docker (optional).

## Run locally

```bash
./run-local-dev.sh
```

Starts the backend on http://localhost:8000 (`/docs` for Swagger) and the frontend on http://localhost:3000,
installing deps and creating `.env` files from the examples on first run. Ctrl+C stops both.

Or with Docker: `docker compose up --build`.

Per-app details: [frontend/README.md](frontend/README.md), [backend/README.md](backend/README.md).

## AI workflow

Rules and skills are generated from [frontend-ai-starter-recipes](https://github.com/JeelVankhede/frontend-ai-starter-recipes)
(`nextjs-shadcn` preset) and adapted from [backend-ai-starter-recipes](https://github.com/JeelVankhede/backend-ai-starter-recipes)
for FastAPI. For non-trivial work run `/think` → `/plan` → `/build` → `/review` → `/test` → `/ship` → `/reflect`.
