# testing_agent

**QA testing agent** for developers: a local dashboard that checks your app on `localhost` before a push.

- **Quick Scan (no AI)** — every page at desktop and mobile size: console errors, failed/slow API calls,
  broken images and links, pages wider than the screen. Screenshots and a Playwright trace per run.
- **Specialist agents (AI)** — QA Lead, Design reviewer, Functionality tester, Code reviewer and Test writer run
  through **Claude Code on your own Claude plan** (`claude -p`, no API key, no per-run bill).
- **To review** — every finding with its evidence; Accept (bug to fix) or Ignore (with a reason).
- **Save as test** — a passing flow becomes a normal Playwright test with the next test ID, opened as a PR.

Plan: [docs/plans/2026-11-17-qa-testing-agent.md](docs/plans/2026-11-17-qa-testing-agent.md).

```
frontend/   Next.js 16 + Tailwind v4 + shadcn/ui (TypeScript)
backend/    FastAPI + Pydantic v2 (Python 3.12, uv)
.claude/    Claude Code rules (per app) + lifecycle skills (/think … /reflect)
docs/plans/ saved implementation plans
```

## Prerequisites

Node.js 22+, [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you), Docker (optional).

## Setup (once per machine)

You need the app under test running on `localhost`, Node.js 22+, uv, and a Claude Pro, Max, Team or Enterprise plan.

1. **Install Claude Code and log in:** run `claude` once and log in with your Claude account.
   `/status` should show your subscription, not an API key.
2. **No API key:** `echo $ANTHROPIC_API_KEY` must print nothing. If it prints a key, remove it from your shell
   profile — agent runs are refused while it is set.
3. **Browser:** `cd backend && uv run playwright install chromium`. On macOS 12, current Playwright can't run its
   own Chromium: set `BROWSER_CHANNEL=chrome` in `backend/.env` to use installed Google Chrome instead.
4. **Configure:** `cp backend/.env.example backend/.env` (the start script does this too) and set at least
   `APP_URL` and `APP_REPO_PATH`. List your pages, risky endpoints, mocks and test folders in
   [`backend/qa/qa.config.json`](backend/qa/qa.config.json). Put design PNGs in [`backend/designs/`](backend/designs/README.md).
5. **Start:** `./run-local-dev.sh` → dashboard http://localhost:4000, backend http://127.0.0.1:8400/docs.
6. **Setup check:** open http://localhost:4000/setup and click **Run a test on my login**; everything should be green.
7. **First run:** Quick Scan, then **Check my change** on a small branch.

Agent runs count toward your plan's usage limits: run Quick Scan first and point agents at the change in hand.

## How it fits together

```
backend/qa/agents/*.md      Claude Code subagent definitions (QA Lead, Design reviewer, …) — portable
backend/qa/qa.config.json   pages, viewports, limits, noise filter, risky endpoints, mocks, login, test folders
backend/qa/init-page.template.ts
                            Playwright MCP init-page per agent run: blocks/mocks risky endpoints and records
                            console errors and failed requests (flow verdicts come from this, not the model)
backend/.qa-runs/<run>/     one folder per run: run.json, events.jsonl, screenshots, traces, Claude stream
```

Every agent run is `claude -p --agents … --agent <name> --mcp-config … --permission-mode dontAsk`, started in
`APP_REPO_PATH` so the app's own `CLAUDE.md`, guidelines and skills load. Never `--bare` (it ignores subscription
logins). The Claude Code version is pinned (`CLAUDE_CODE_VERSION`); re-check after upgrades.

Docker (`docker compose up --build`) serves the dashboard only; real runs need `./run-local-dev.sh`.

Per-app details: [frontend/README.md](frontend/README.md), [backend/README.md](backend/README.md).

## Using it from other AI coding tools

The dashboard isn't the only way in — the backend (`./run-local-dev.sh`, port 8400) is reachable
from wherever you're already working:

- **Claude Code (CLI or the VS Code extension):** `/qa-run` — a skill at
  [`.claude/skills/qa-run/SKILL.md`](.claude/skills/qa-run/SKILL.md) (also installed at
  `~/.claude/skills/qa-run/` so it works from *any* repo open in Claude Code, not just this one).
  Type `/qa-run` for a Quick Scan, or `/qa-run check <describe the flow>` for Check my change.
- **Cursor, Antigravity, Windsurf, or any other MCP-compatible tool:** an MCP server at
  `backend/src/app/mcp_server.py` (run with `uv run qa-mcp-server`), exposing `quick_scan`,
  `check_change`, `get_run` and `list_open_findings` as tools — the same four building blocks
  the skill above uses, just over MCP instead of a markdown playbook. Cursor picks this up
  automatically from [`.cursor/mcp.json`](.cursor/mcp.json). For another tool, add the same
  block to wherever *it* keeps MCP server config (check that tool's own docs for the file —
  it's usually `mcpServers: { "qa-testing-agent": { "command": "uv", "args": ["run",
  "qa-mcp-server"], "cwd": "backend" } }`, the same shape Claude Desktop and Cursor both use).

Either way, the backend has to be running first (`./run-local-dev.sh`) — both of these are
clients of its API, not a replacement for it, so there's exactly one place deciding what's safe
to run (risky-endpoint blocking, the billed-credential refusal, etc.).

## AI workflow

Rules and skills are generated from [frontend-ai-starter-recipes](https://github.com/JeelVankhede/frontend-ai-starter-recipes)
(`nextjs-shadcn` preset) and adapted from [backend-ai-starter-recipes](https://github.com/JeelVankhede/backend-ai-starter-recipes)
for FastAPI. For non-trivial work run `/think` → `/plan` → `/build` → `/review` → `/test` → `/ship` → `/reflect`.
