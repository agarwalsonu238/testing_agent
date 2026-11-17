# Plan: QA testing agent (first version, developers, local only)

- **Date:** 2026-11-17
- **Status:** approved (implements "QA Testing Agent: Plan for Local Testing (v3)", 13 Nov 2026)
- **Sides:** both
- **Ticket / request:** "implement this plan" — web-qa-agent-mvp-plan.md v3

## Goal

A local dashboard (this monorepo) that runs Quick Scan (no AI) and a team of Claude Code agents
(`claude -p`, developer's own subscription) against an app on `localhost`, and collects findings in one
**To review** list.

- [x] Setup check page (Claude Code + pinned version, login type, no API key, browser, app reachable, app repo, designs)
- [x] Quick Scan: pages × desktop/mobile, console errors, page crashes, failed/slow API calls, broken images and links, overflow, slow pages; screenshots + Playwright trace; dev-server noise filter; mocked / real mode
- [x] Agent runner on `claude -p` (stream-json, `--agents`, `--agent`, `--mcp-config`, `--permission-mode dontAsk`), refuses when `ANTHROPIC_API_KEY` is set and aborts when Claude Code reports any `apiKeySource` other than `none`; never `--bare`
- [x] Five agents: QA Lead, Design reviewer, Functionality tester, Code reviewer, Test writer
- [x] To review with Accept / Ignore (reason required; ignored fingerprints are skipped next time)
- [x] Report page: verdict word, failure categories, severities, evidence, live progress, PR summary text
- [x] Save as test: next test ID, registry entry, new branch in a separate worktree, PR via `gh` when available
- [x] Saved tests: list from the registry, re-run with plain Playwright (no AI)

## Out of scope

Everything in "Out for now" of the source plan (QA rollout, later agents, hosted version, Firefox/Safari, visual baselines, chat posting, auto-merge).

## Decisions taken from the source plan's recommended defaults (section 14)

| Open decision | Default implemented | Where to change |
|---|---|---|
| Design source | Exported PNGs in `DESIGNS_DIR`; Figma MCP only if `FIGMA_MCP_URL` is set | `.env` |
| Dashboard | This monorepo | — |
| Default run mode | `mocked` | UI selector per run |
| Saved-test folder | isolated | `qa/qa.config.json` → `tests.default_folder` |
| Mobile size | every scan | `qa/qa.config.json` → `viewports` |
| Who reviews saved-test PRs / where bugs go | not automated (PR is opened; nothing merges) | — |

## Approach

- **Backend** (`backend/src/app/`): `integrations/` wraps the outside world (Claude Code CLI, Playwright, git, `gh`, HTTP probe);
  `services/` hold logic (run store, run manager, quick scan rules, agent runs, QA Lead selection, test writer, findings/ignore list, setup check);
  `api/routes/` are thin. Runs execute as one in-process asyncio task at a time (local single-user tool — no queue);
  every run is a folder under `RUNS_DIR` (`run.json`, `events.jsonl`, screenshots, traces, raw Claude stream); the newest 20 are kept.
  A run left `running` by a backend restart is marked BLOCKED on startup.
- **Agents** are Claude Code subagent markdown files in `backend/qa/agents/` (portable), compiled to the `--agents` JSON per run.
  Each agent's `tools` are its only tools; the runner pre-approves read-only and Playwright MCP tools and, for the Test writer only, `Edit(<tests dir>/**)`. `dontAsk` denies the rest.
- **Flow verdicts come from Playwright, not the model:** each agent run gets a generated Playwright MCP `--init-page` that blocks/mocks risky endpoints
  (same list as Quick Scan) and records console errors, page crashes and failed requests to a log. The Functionality tester's verdict = recorded
  failures + failed `browser_wait_for` checks; no recorded check → BLOCKED.
- **Frontend** (`frontend/src/`): App Router pages with a sidebar layout; data via `apiFetch` helpers in `lib/api.ts` and a small polling hook.

## Machine notes found while building

- Current Playwright (1.65) does not support its own Chromium on macOS 12. Set `BROWSER_CHANNEL=chrome` to use installed Google Chrome (Quick Scan and Playwright MCP).
- Playwright for Python's bundled Node driver can fail on macOS 12; `run-local-dev.sh` falls back to system Node via `PLAYWRIGHT_NODEJS_PATH`.
- Ports: dashboard moves to FE **4000** / BE **8400** (bound to `127.0.0.1`) so it doesn't clash with the app under test on 3000/8000.

## API contract (`/api/v1`)

| Method | Path | Request | Response | Errors |
|---|---|---|---|---|
| GET | `/setup-check?live=bool` | — | `SetupCheck` | — |
| GET | `/qa-config` | — | `QaConfigSummary` (app URL, pages, agents) | — |
| POST | `/runs/quick-scan` | `{mode}` | 202 `RunDetail` | 409 busy, 412 API key set |
| POST | `/runs/check-change` | `{mode, base_ref?, flow?}` | 202 `RunDetail` | 409, 412 |
| POST | `/runs/agent` | `{agent, task, route?, mode}` | 202 `RunDetail` | 404 agent, 409, 412, 422 |
| GET | `/runs` | — | `RunSummary[]` | — |
| GET | `/runs/{id}` | — | `RunDetail` | 404 |
| GET | `/runs/{id}/events?after=n` | — | `{events, done}` | 404 |
| GET | `/runs/{id}/files/{path}` | — | file | 404 |
| POST | `/runs/{id}/cancel` | — | `RunDetail` | 404, 409 not running |
| POST | `/runs/{id}/save-test` | `{title?, folder?}` | 202 `RunDetail` (new run) | 404, 409 not a passing flow |
| GET | `/findings?status=&agent=` | — | `FindingItem[]` | — |
| POST | `/runs/{id}/findings/{fid}/decision` | `{decision: accept\|ignore, reason?}` | `Finding` | 404, 422 ignore without reason |
| GET | `/saved-tests` | — | `SavedTest[]` | 412 no app repo |
| POST | `/saved-tests/{test_id}/run` | — | 202 `RunDetail` | 404, 409 |

## Approval needed for

New backend runtime deps `playwright` and `httpx` (both named by the source plan). No frontend deps.

## Test plan

- Backend unit: quick-scan rules + noise filter, ignore fingerprints, QA Lead change classification, test-ID allocation, stream-json parsing and flow verdicts, API-key refusal.
- Backend API: setup check, run lifecycle with a fake job, findings decisions (422 without reason), file traversal, save-test preconditions.
- Backend browser: Quick Scan against a local fixture site with a planted 500 API call, broken image and overflow (skipped when no browser).
- Frontend: finding card (ignore requires a reason), verdict badge, findings board filter.
- Manual: start with `./run-local-dev.sh`, Setup check, Quick Scan against a planted-bug page.
