# QA Testing Agent: status of the first version

**Date:** 17 Nov 2026 · **Branch:** `feat/qa-testing-agent` · **Source plan:** QA Testing Agent: Plan for Local Testing (v3, 13 Nov 2026)
**Implementation plan:** [docs/plans/2026-11-17-qa-testing-agent.md](plans/2026-11-17-qa-testing-agent.md)

## Summary

All four build phases from the plan are implemented in this monorepo:

- Setup check and Quick Scan
- agents on Claude Code
- Design reviewer and QA Lead
- Test writer

Every automated check passes: 46 backend tests, 11 frontend tests, lint, type checks and the production build.
Quick Scan and the Code reviewer were also run for real on a developer machine with a Claude Pro login.
The Functionality tester, Design reviewer, QA Lead and Test writer haven't had a real run yet (see [Pending](#pending)).

## What changed

### Backend (`backend/`, FastAPI)

| Area | Files | What it does |
|---|---|---|
| Settings | `src/app/core/config.py`, `.env.example` | App under test (`APP_URL`, `APP_REPO_PATH`, `DESIGNS_DIR`), run storage, pinned Claude Code version, MCP packages, browser channel, shared test account, Save-as-test options. Detects `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` and strips them from every child process |
| Errors | `src/app/core/errors.py`, `src/app/main.py` | Domain errors mapped to 404 / 409 / 412; lifespan creates the HTTP client; a run left running by a restart is marked BLOCKED |
| Integrations | `src/app/integrations/` | `claude_code.py` (`claude -p` with stream-json, `--agents`, `--agent`, `--permission-mode dontAsk`; never `--bare`; stops if `apiKeySource` isn't `none`), `browser.py` (Playwright), `git.py` (diff, worktree, commit, push, `gh pr create`), `http_probe.py`, `process.py` |
| Run store | `services/run_store.py`, `services/run_manager.py` | One folder per run under `.qa-runs/` (`run.json`, `events.jsonl`, evidence). Last 20 kept. One run at a time; cancel supported |
| Quick Scan | `services/quick_scan.py` | Every page in the config at desktop and mobile size. Findings for crashes, failed/slow API calls, console errors, broken images/links, horizontal overflow, slow pages. Noise filter, mocked/real mode, risky endpoints blocked, screenshots and Playwright traces |
| Agents | `services/agents.py`, `qa/agents/*.md` | Five Claude Code subagent definitions. Per-run MCP config and a generated Playwright init-page (`qa/init-page.template.ts`) that mocks/blocks risky endpoints and records console errors and failed requests. Report parsing, evidence that can't leave the run folder, flow verdict from recorded checks |
| QA Lead | `services/qa_lead.py` | Diff against `DIFF_BASE`, fixed rule for which agents run, the QA Lead adds routes, flow and review focus |
| Save as test | `services/test_writer.py`, `services/saved_tests.py` | Next test ID, registry entry, separate worktree on a new branch, writes only in the test folder, first run without AI, push + PR. Saved tests re-run with plain Playwright |
| Findings | `services/findings.py` | Fingerprints, ignore list (`.qa-runs/ignored.json`), verdicts (Warnings don't fail a run) |
| Setup check | `services/setup_check.py` | Claude Code + pinned version, subscription login (`claude auth status`), no API key, optional one-line login test, browser, Node, app reachable, app repo, config, agents, designs |
| API | `api/routes/{setup,runs,findings,saved_tests}.py`, `api/deps.py` | Contract in the implementation plan |
| Config | `qa/qa.config.json`, `designs/README.md` | Pages, viewports, limits, noise filter, risky endpoints, mocks, login, test folders |
| Dependencies | `pyproject.toml`, `uv.lock` | Added `playwright`; `httpx` is now a runtime dependency |

### Frontend (`frontend/`, Next.js)

| Route | What it shows |
|---|---|
| `/` | To review: open findings grouped by run, tabs per agent, Accept / Ignore (reason required) |
| `/check` | Check my change: optional flow, compare-against ref, run mode |
| `/scan` | Quick Scan: run mode |
| `/agents/[name]` | Run one agent (route required for the Design reviewer) |
| `/runs`, `/runs/[id]` | Run list; report with verdict, live progress, QA Lead plan, agent steps and recorded checks, findings with screenshots and designs side by side, traces, PR summary to copy, Save as test |
| `/saved-tests` | Registry list, run a saved test without AI |
| `/setup` | Setup check, plus a button for the one-line login test |
| `/guide` | How to use it, verdicts, severities, safety rules |

Supporting files: `src/lib/api.ts` (typed client), `src/hooks/use-api-data.ts` (loading/error/polling), `src/components/*`.
No new frontend dependencies.

### Repo-level

- `run-local-dev.sh`: the dashboard now runs on port **4000** and the backend on **8400**, both bound to `127.0.0.1`, so they don't clash with the app under test on 3000/8000. Warns when an API key is set. Falls back to system Node when Playwright's bundled driver can't run (macOS 12).
- `docker-compose.yml`, `backend/Dockerfile`, `.gitignore` (`.qa-runs/`), `README.md` (setup steps), `CLAUDE.md` (ports).
- Two small existing bugs fixed:
  - `globals.css` mapped `--font-sans` to itself, so text rendered in a serif fallback instead of Geist.
  - `vitest.setup.ts` had no Testing Library cleanup between tests.

## Test cases

### Backend: 46 tests (`cd backend && uv run pytest`)

| File | Test case | Checks that… |
|---|---|---|
| `tests/unit/test_quick_scan_rules.py` | clean page | a clean page has no findings |
| | API 500 / 4xx | 5xx is High, 4xx is Medium |
| | failed request vs guard block | network failures are High; our own risky-endpoint blocks are not findings |
| | slow API and page | > 2 s API and > 5 s page are Warnings |
| | noise filter | HMR/dev-server messages and Chrome's "Failed to load resource" echo are dropped; duplicates merged |
| | overflow, broken image, page error | mobile overflow and broken image are Medium, uncaught error is High |
| | app down | navigation failure is High with category `environment` |
| | location and screenshot | findings carry `route · viewport` and the screenshot |
| `tests/unit/test_findings.py` | fingerprint | ignores numbers and case (line numbers, status codes) |
| | ignore list | an ignored finding is auto-ignored next time with the old reason |
| | verdict | High/Medium fail a run; Warnings and ignored findings don't |
| | combined verdict | FAILING beats BLOCKED beats PASS |
| `tests/unit/test_claude_stream.py` | JSON extraction | finds the report in bare JSON, a ```json fence, or prose |
| | stream parser | collects tool calls, errors, result, permission denials |
| | missing result | a stream without a result is an error |
| | image scrubbing | base64 screenshots aren't written to the raw log |
| | argv | never `--bare`, `dontAsk` mode, agent selected, prompt not in argv |
| | child env | API-billing variables are stripped from subprocesses |
| | settings | API key detected without exposing its value |
| `tests/unit/test_agents.py` | shipped agents | all five load; reviewers can't Write/Edit/Bash |
| | Test writer permissions | writes only via `Edit(<tests dir>/**)`; Bash and `browser_run_code_unsafe` denied |
| | agent file parsing | frontmatter required |
| | flow verdict | passing `browser_wait_for` → PASS; retried check counts its last result; failed check → FAILING; no checks → BLOCKED |
| | recorder log | console errors and 5xx become failed checks; guard blocks and noise don't |
| | Playwright code | the code Playwright MCP ran is extracted for Save as test |
| | evidence safety | files outside the run folder are never served |
| | report findings | severity/category normalised; design PNG attached |
| | network guard | mocks answer first; risky endpoints blocked; no mocks in real mode |
| | init-page and MCP config | placeholders filled; MCP version pinned; optional servers stay off |
| | change classification | UI → Design reviewer, logic → Functionality tester, always Code reviewer; docs-only change runs nothing |
| | test IDs and registry | next free ID (`QA-012` → `QA-013`); registry round trip; slugs |
| `tests/api/test_runs_api.py` | Quick Scan with app down | 202, then BLOCKED with reason; events numbered; listed with counts |
| | bad IDs | unknown run 404, invalid ID rejected |
| | file traversal | `../` out of a run folder is 404 |
| | Accept / Ignore | ignore without a reason is 422; ignored finding remembered; unknown finding 404 |
| | Save as test | 409 unless the run has a passing Functionality tester flow |
| | API key set | agent runs refused with 412; key value never in the response |
| | validation | unknown agent 404, invalid body 422 |
| | cancel | cancelling a finished run is 409 |
| | QA config | agents, pages and viewports listed |
| | saved tests | 412 without an app repo |
| `tests/api/test_setup_api.py` | setup check | each item reported; login test skipped unless asked |
| | live check | runs the one-line login test |
| | API key login | login and API-key items fail; login test skipped; key value never returned |
| `tests/browser/test_quick_scan_browser.py` | planted bugs (real browser) | 500 API call, broken image, broken link, console error at both sizes; mobile overflow; clean page has no findings; HMR noise filtered; risky POST never reaches the server; screenshots and traces saved; session file removed |
| `tests/test_health.py` | health | existing health endpoint unchanged |

The browser test needs a working browser and skips otherwise. On macOS 12 run it with
`BROWSER_CHANNEL=chrome PLAYWRIGHT_NODEJS_PATH=$(which node) uv run pytest`.

### Frontend: 11 tests (`cd frontend && npm test`)

| File | Test case |
|---|---|
| `finding-card.test.tsx` | page screenshot and design shown side by side |
| | Ignore needs a reason; no API call without one |
| | Ignore with a reason sends the decision and shows it |
| | backend error message shown when a decision fails |
| `findings-board.test.tsx` | open findings grouped by run, linked to the report |
| | agent tab in the URL filters the list |
| | retryable error when the backend is down |
| `badges.test.tsx` | verdict word (or RUNNING); severity shown as a word, not colour only |
| `backend-status.test.tsx` | existing health widget, success and failure |

### Manual checks done on a developer machine (macOS 12, Claude Pro)

| Check | Result |
|---|---|
| Setup check | All green: Claude Code 2.1.323, Pro login, no API key, Chrome 150, Node, app reachable, app repo, config, agents |
| Quick Scan on a planted-bug page | FAILING, with the 404 API call, broken image, console error, overflow at both sizes; screenshots and traces saved |
| Code reviewer on a planted buggy diff | Found the ZeroDivisionError and IndexError on empty lists, the behaviour change and missing tests, with file:line. Ran on the subscription (`apiKeySource: none`); repo left untouched |
| Dashboard pages at 1440×900 and 390×844 | No console errors, no horizontal overflow |
| Generated Playwright init-page | Type-checks under strict TypeScript; against a fake page it mocks, blocks and logs as expected |

## Pending

### Not yet verified for real

- **Functionality tester, Design reviewer, QA Lead and Test writer.** They need Playwright MCP (`npx @playwright/mcp@0.0.85`), which wasn't run during the build. Their logic is covered by unit tests. The first real *Check my change* on the app is the remaining end-to-end test. Watch for:
  - Playwright MCP accepting the generated `--init-page` (dynamic `import('node:fs')` inside it)
  - Claude Code's `--agents` tool lists accepting `mcp__playwright__*` names
  - the `Edit(<tests dir>/**)` permission rule matching paths relative to the worktree
- **Real-backend mode** with `TEST_ACCOUNT_*` and the login form in `qa.config.json`.
- **Save as test end to end:** push and `gh pr create` on a real repo, and the first run in the worktree with the borrowed `node_modules`.
- **Figma MCP** (`FIGMA_MCP_URL`) and **Chrome DevTools MCP** (off by default).

### Configuration each team needs to fill in

- `backend/qa/qa.config.json`:
  - the app's page list and risky endpoints (the defaults are guesses)
  - its mocks or `mocks_file`, and the mock-login storage state
  - its test folders, registry path and Playwright command
- `backend/designs/`: design PNGs named after routes.
- `backend/.env`: `APP_URL`, `APP_REPO_PATH`. On macOS 12, `BROWSER_CHANNEL=chrome`.

### Known limitations

- One run at a time, as an in-process task. A backend restart marks the running run BLOCKED rather than resuming it.
- Chrome DevTools MCP drives its own browser, which the risky-endpoint guard doesn't cover. It stays off until that's solved.
- The Functionality tester's verdict needs at least one `browser_wait_for` check; flows with no visible text to check end as BLOCKED.
- No visual regression baselines and no Firefox/Safari (out of scope in the plan).

### Decisions still open from the plan (section 14)

The defaults below are implemented and can be changed by config:

| Decision | Implemented default |
|---|---|
| Approve v3 (subscription, developers first, specialist agents) | Built as v3 |
| Claude plan per developer | — (usage counts toward each plan's limits) |
| Design source | PNGs; Figma MCP optional |
| Dashboard | This monorepo |
| Next agents after the first five | — |
| Default run mode | Mocked API |
| Default saved-test folder | Isolated |
| Who reviews saved-test PRs | — (PR is opened; nothing merges automatically) |
| Where bugs are filed | — (Accept marks a bug; no tracker integration) |
| Mobile size on every scan | Yes |
| Phase dates | — |

### After developers approve (from the plan)

QA team rollout and the daily-run link, real-backend mode for QA, and the later agents (accessibility, performance, API checker, security, content, bug writer).
