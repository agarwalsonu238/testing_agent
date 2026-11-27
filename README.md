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
   `APP_URL` and `APP_REPO_PATH` (the default project; each run can point at another one). That's enough
   for any project: with no pages listed, Quick Scan discovers them by following links from `/`. To tune a
   project, add [project settings](#project-settings-qaqaconfigjson) to *its* repo, not to this one.
5. **Start:** `./run-local-dev.sh` → dashboard http://localhost:4000, backend http://127.0.0.1:8400/docs.
6. **Setup check:** open http://localhost:4000/setup and click **Run a test on my login**; everything should be green.
7. **First run:** Quick Scan, then **Check my change** on a small branch.

Agent runs count toward your plan's usage limits: run Quick Scan first and point agents at the change in hand.

## How it fits together

```
backend/qa/agents/*.md      Claude Code subagent definitions (QA Lead, Design reviewer, …) — portable
backend/qa/qa.config.json   the tool's generic defaults: viewports, limits, framework noise, generic risky endpoints
<project>/.qa/qa.config.json
                            optional, in the tested repo: its pages, risky endpoints, mocks, login, test folders
<project>/.qa/designs/      optional, in the tested repo: design PNGs (else DESIGNS_DIR)
backend/qa/init-page.template.ts
                            Playwright MCP init-page per agent run: blocks/mocks risky endpoints and records
                            console errors and failed requests (flow verdicts come from this, not the model)
backend/.qa-runs/<run>/     one folder per run: run.json, events.jsonl, screenshots, traces, Claude stream
```

Every agent run is `claude -p --agents … --agent <name> --mcp-config … --permission-mode dontAsk`, started in
`APP_REPO_PATH` so the app's own `CLAUDE.md`, guidelines and skills load. Never `--bare` (it ignores subscription
logins). The Claude Code version is pinned (`CLAUDE_CODE_VERSION`); re-check after upgrades.

### A different AI for the review stage (optional)

A run goes plan → review → (your approval) → run → report. Plan, run and report always use Claude, because they
need your repo and the browser. The **review** stage only reads the draft test cases, so it can be done by another
AI. In `backend/.env`:

```
REVIEWER_PROVIDER=gemini            # claude (default) | gemini | perplexity | openai | custom
REVIEWER_MODEL=<a model name from that provider>
REVIEWER_API_KEY=<that provider's key>
# custom only: REVIEWER_BASE_URL=https://your-llm.example.com/v1   (any OpenAI-compatible API)
```

Restart the backend; the Setup check shows who reviews, and the run's Review tab says "Reviewed by …". It is billed
to that provider's key, not your Claude plan. It is sent the draft cases (title, steps, expected), never the diff or
your flow text, but a code-review case can quote a changed line, so those lines reach the provider. If the provider
fails, Claude reviews instead and the run says so.

Docker (`docker compose up --build`) serves the dashboard only; real runs need `./run-local-dev.sh`.

Per-app details: [frontend/README.md](frontend/README.md), [backend/README.md](backend/README.md).

## Project settings (`.qa/qa.config.json`)

Nothing about the app under test lives in this repo. Each project can keep its own settings in a
`.qa/qa.config.json` at its repo root; the run that targets that project reads it, and no other run does.
It's laid over the tool's defaults in [`backend/qa/qa.config.json`](backend/qa/qa.config.json):

| Keys | Rule |
|---|---|
| `noise_filter`, `risky_endpoints`, `mocks` | added to the defaults (a project can't drop a default safety rule) |
| `limits`, `auth`, `tests`, `changes` | field by field: set only what differs |
| anything else (`pages`, `viewports`, `api_checks`, …) | replaces the default |

```json
{
  "pages": [{ "path": "/", "name": "Home" }, { "path": "/pricing", "name": "Pricing" }],
  "risky_endpoints": [{ "url": "*/api/billing/*", "method": "POST" }],
  "tests": { "isolated_dir": "frontend/tests/e2e/isolated", "pr_base": "dev" }
}
```

Leave `pages` out and Quick Scan discovers up to `limits.max_pages` (15) same-site pages from links. Put
design PNGs in the project's `.qa/designs/` ([naming](backend/designs/README.md)). The Setup check
shows which settings applied.

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

## Deploying (e.g. Render), so you're not starting it locally every time

This tool was built to run locally — deploying it changes a few things, not just where it runs:

- **It becomes reachable by anyone with the URL.** Set `API_AUTH_TOKEN` on the backend once it's
  not bound to `127.0.0.1` any more; every `/api/v1` request then needs a matching `X-API-Key`
  header (or `?key=` — screenshots load via `<img>`, which can't send headers). Pick a long
  random value. Note the frontend's copy of it (`NEXT_PUBLIC_QA_API_KEY`) ends up in the browser
  bundle — real access control, not a secret a sufficiently motivated person can't extract.
- **Check my change and the API checker need their own checkout of the app repo** — a server has
  no local working tree to diff. Set `APP_REPO_GIT_URL` (+ `APP_REPO_GIT_TOKEN` for a private
  repo, + `APP_REPO_GIT_REF` for which branch, default `main`); the container clones/refreshes
  it on every start (`backend/docker-entrypoint.sh`). This means Check my change there diffs
  **whatever's pushed to that branch**, not your local uncommitted work — push first, then run
  it. (Save as test still needs a writable local repo, so it isn't available this way.)
- **Claude Code needs to log in without a terminal.** Run `claude setup-token` locally (on your
  own subscription) and set the result as `CLAUDE_CODE_OAUTH_TOKEN` on the deployed backend.
- **`APP_URL` has to be a URL the server can reach** — not `localhost:3000`. A deployed/staging
  URL for the app under test (which you're likely already using) is fine.
- **Playwright needs real RAM.** Render's free tier (~512MB) is a real risk for headless
  Chromium — expect to need a paid instance type for Check my change / Quick Scan to be
  reliable; test Quick Scan first since it's the lighter of the two.
- **Free-tier disk is ephemeral** — run history/screenshots may not survive a redeploy or a
  sleep/wake cycle. Fine if you don't need that history kept.

### Steps (Render, manual — more reliable than guessing at Blueprint YAML cross-service wiring)

1. **Backend** → New → Web Service → connect this repo → Runtime: **Docker** → Dockerfile path
   `backend/Dockerfile`, context `backend`. Add env vars: `API_AUTH_TOKEN` (pick a value),
   `CLAUDE_CODE_OAUTH_TOKEN`, `APP_URL`, `APP_REPO_GIT_URL` (+ token/ref if needed),
   `CORS_ORIGINS` (the frontend's URL, once you know it — you can redeploy to fix this after
   step 2). Deploy, then note its `https://….onrender.com` URL.
2. **Frontend** → New → Web Service → same repo → Dockerfile path `frontend/Dockerfile`, context
   `frontend`. Build args (not plain env vars — Next.js inlines `NEXT_PUBLIC_*` at build time):
   `NEXT_PUBLIC_BACKEND_URL` = the backend's URL from step 1, `NEXT_PUBLIC_QA_API_KEY` = the
   same value as `API_AUTH_TOKEN`. Deploy, then go back and set the backend's `CORS_ORIGINS` to
   `["https://<this-frontend-url>"]` and redeploy the backend.
3. **MCP/skill config** — point whichever tool you use at the deployed backend instead of
   localhost: set `MCP_BACKEND_URL` / `MCP_DASHBOARD_URL` in the backend's own `.env` (used by
   `qa_mcp_server.py` when *it* still runs locally, spawned by Cursor/Claude Code as usual, just
   talking to the deployed API) — or, if running `qa-mcp-server` itself elsewhere too, set
   `MCP_BACKEND_URL`/`MCP_DASHBOARD_URL` wherever that process's env comes from.

Docker build locally first if you want to catch a Dockerfile problem before Render does:
`docker build -t qa-backend ./backend` (this adds Node + Chromium + Claude Code to the image, so
expect it to take a few minutes and produce a multi-GB image).

## AI workflow

Rules and skills are generated from [frontend-ai-starter-recipes](https://github.com/JeelVankhede/frontend-ai-starter-recipes)
(`nextjs-shadcn` preset) and adapted from [backend-ai-starter-recipes](https://github.com/JeelVankhede/backend-ai-starter-recipes)
for FastAPI. For non-trivial work run `/think` → `/plan` → `/build` → `/review` → `/test` → `/ship` → `/reflect`.
