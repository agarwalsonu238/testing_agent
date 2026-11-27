# Plan: Generic tool, per-project QA config

- **Date:** 2026-11-27
- **Status:** approved (2026-11-27)
- **Sides:** backend (frontend: copy only)
- **Ticket / request:** "Make this generic, not specific to any one app or path, so any project can be tested independently."

## Goal

The tool ships with generic defaults only. Anything specific to one app lives in that app's repo, in
`<repo>/.qa/qa.config.json` (and `<repo>/.qa/designs/`), and is picked up for whichever project a run
targets. A project with no `.qa/` folder, or a bare URL with no repo, still gets a useful run: Quick
Scan discovers pages by following same-site links.

- [ ] `backend/qa/qa.config.json` holds no app-specific pages, endpoints, test folders or branches.
- [ ] A run against repo X reads `X/.qa/qa.config.json` merged over the tool defaults. A run against
      repo Y never sees X's settings.
- [ ] With no pages configured, Quick Scan starts at `/`, follows same-origin links, and scans up to
      `limits.max_pages` (default 15) pages at every viewport.
- [ ] Design PNGs come from `<repo>/.qa/designs/` when that folder exists, else `DESIGNS_DIR`.
- [ ] Setup check says which config applied ("tool defaults" or "tool defaults + <repo>/.qa/qa.config.json")
      and whether pages are listed or discovered.
- [ ] The previous app's values (its page list, app-specific risky endpoints, test folders,
      `pr_base`, a vendor-specific noise filter) are dropped from this repo. **Decision:** dropped,
      not moved into that app's repo; it
      runs on discovery and the generic defaults.

## Out of scope

- Detecting a repo's default branch for `pr_base` (stays `main` unless the project sets it).
- Crawling behind a login, or crawling beyond one origin.
- Per-project agent definitions (`qa/agents/*.md` are already generic).
- Changing `.env` handling: `APP_URL` / `APP_REPO_PATH` stay the local defaults; per-run overrides
  already exist in the form.

## Approach

### 1. Config layering (`services/qa_config.py`)

`load_qa_config(settings)` becomes: tool defaults (`backend/qa/qa.config.json`, or schema defaults if
missing) → overlaid with `<app_repo_path>/.qa/qa.config.json` when it exists → then the existing
`mocks_file` merge. Merge rules, chosen so a project can't silently weaken the tool's safety rules:

| Field | Rule |
|---|---|
| `noise_filter`, `risky_endpoints`, `mocks` | **concatenated** (tool's + project's) |
| `pages`, `viewports`, `api_checks.endpoints` | project value **replaces** when present |
| `limits`, `auth`, `tests`, `changes` | **field-by-field** overlay (only keys the project sets) |
| everything else | project value replaces when present |

Implemented as a dict merge on the raw JSON (only keys present in the project file count), then one
`QaConfig.model_validate`. An invalid project file raises `PreconditionError` naming that file, like
today. `retarget()` already reloads the config per run, so per-run project folders just work.

### 2. Generic tool defaults (`backend/qa/qa.config.json`)

Keep: viewports, limits, the framework noise (HMR, Fast Refresh, Vite, React DevTools, favicon), the
generic CSP report-only warning, `api_url_pattern`, and generic risky globs (`*payment*`,
`*refund*`, `*payout*`, any `DELETE` under `*/api/*`, `POST/PUT/PATCH` under `*/api/admin/*`).
Remove: the page list, the app-specific risky endpoints, the vendor-specific CSP-report host, and
the whole `tests` block (schema defaults apply: `tests/e2e/...`, `main`).

### 3. Page discovery (`services/quick_scan.py`, `integrations/browser.py`)

- `QaConfig.pages` default changes from `[Home]` to `[]` (empty = discover); `Limits.max_pages = 15`.
- `scan_page` already collects `a[href]` for the broken-link check; it also returns them as
  `PageObservation.links`.
- Quick Scan, first viewport: breadth-first from `/`. Each scanned page's links are filtered to the
  same origin, de-duplicated by path (query and hash dropped), and skipped when they look like
  files (`.pdf`, `.zip`, images…), match the existing skip list, or the guard would block them.
  This stops at `max_pages`. The other viewports scan the same discovered list.
- Page names come from the path (`/pricing` → "Pricing"). The event log says "Discovered N pages
  from links" and lists them.
- Listed `pages` work exactly as today (no discovery).

### 4. Per-project designs

A small `designs_dir(settings)` helper returns `<repo>/.qa/designs` if it exists, else
`settings.designs_dir`. `list_designs`, `design_files`, the QA Lead's `add_dirs` and its
"no design PNG" messages all use it.

### 5. Setup check, docs, copy

- Setup "QA config" row: source(s) and "N page(s) listed" / "pages discovered from links (up to N)".
- README "Configure" step and `backend/README.md`: document `.qa/qa.config.json` with a minimal
  example and the merge rules. `.env.example`: `DESIGNS_DIR` comment notes the per-project folder.
- Frontend: Quick Scan page intro mentions discovery when no pages are listed (copy only).

## File impact map

| File | Change |
|---|---|
| `backend/src/app/services/qa_config.py` | modify: layered load + merge, `designs_dir()`; `list_designs`/`design_files` use it |
| `backend/src/app/schemas/qa_config.py` | modify: `pages` default `[]`, `Limits.max_pages` |
| `backend/src/app/integrations/browser.py` | modify: `PageObservation.links` |
| `backend/src/app/services/quick_scan.py` | modify: discovery when `pages` is empty |
| `backend/src/app/services/qa_lead.py` | modify: designs folder via `designs_dir()` |
| `backend/src/app/services/setup_check.py` | modify: config source + page mode in the row |
| `backend/qa/qa.config.json` | modify: generic defaults only |
| `backend/tests/unit/test_qa_config.py` (or existing config tests) | add: merge rules, invalid project file, no repo |
| `backend/tests/unit/test_quick_scan*.py` | add: link filtering/dedupe and the page cap (pure function) |
| `backend/.env.example`, `README.md`, `backend/README.md` | modify: docs |
| `frontend/src/app/scan/page.tsx` | modify: one line of copy |

## API contract

No change. `GET /api/v1/qa-config` keeps its shape. `pages` is `[]` when pages are discovered;
the frontend only types this field and never renders it.

## Data / state delta

There's no database. Config precedence is new: tool defaults < project `.qa/qa.config.json` <
`mocks_file`. The schema default for `pages` changes, which affects anyone running without a
config file: they get discovery instead of `/` only.

## Risks & tradeoffs

- **Crawling touches more of a live site.** It's GET navigation only, through the same
  risky-endpoint guard, same origin, capped at 15. Logout-style links are a risk: the existing
  skip list is reused and `logout|signout|sign-out` gets added to it.
- **Concatenating safety lists means a project can't remove a tool rule.** That's intended. A
  project that really needs to can still edit the tool defaults.
- **Discovery order isn't fully stable between runs** (links can change). Runs record the list
  they used.
- Agents run with `cwd` = the project repo, so `.qa/` is visible to them. That's harmless, since
  it's config.

## Approval needed for

- **The previous app's values.** Option A: move them into that app's repo as `.qa/qa.config.json`
  (uncommitted, for its owner to review). Option B: drop them and let discovery and the defaults
  handle it. **Chosen: B.**
- Changing the default from "scan `/`" to "discover" (you chose this; noted for the record).

## Test plan

- Backend: `uv run ruff format --check . && uv run ruff check . && uv run mypy src tests && uv run pytest`. New cases:
  merge rules (concat vs replace vs overlay), project file absent, no repo, invalid project file → 412
  with the path, `designs_dir` fallback, link filter (cross-origin, file extensions, hash/query dedupe,
  logout skip, guard-blocked), discovery cap.
- Frontend: `npm run lint && npm run typecheck && npm test && npm run build`.
- Manual: Quick Scan of a real app with no project file shows "Discovered N pages" and no 404s from
  made-up paths; the same scan with a `.qa/qa.config.json` in its repo uses its listed pages; the
  Setup check shows the config source both ways.
