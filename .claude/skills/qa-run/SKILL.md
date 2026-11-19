---
name: qa-run
description: "Run the QA testing agent (Quick Scan or Check my change) straight from a terminal — including the VS Code integrated terminal — without opening the web dashboard. Starts agents on the developer's own Claude Code subscription, plans test case scenarios first, then tests them, and prints the verdict and findings here. Use when the user invokes /qa-run, or asks to run/trigger a QA check, quick scan, or test the app (or a specific flow) from the terminal/CLI."
---

# QA run (terminal)

Drives the QA testing agent backend (`backend/`) from this Claude Code session instead of the
`frontend/` dashboard — useful when the developer is already at a terminal (including the one
VS Code's Claude Code extension opens) and wants a QA run without switching to a browser. It's
the same backend the dashboard calls, so it uses the developer's own Claude subscription (never
an API key — see `backend/src/app/core/config.py`'s `BILLED_CREDENTIAL_VARS`) and the same
scenario-first flow: Check my change always plans test case scenarios (normal path + edge cases)
before anything runs, and tests every one of them before the slower code/design review.

`$ARGUMENTS` (the text after `/qa-run`) says what to run. Read it loosely:
- Empty, or "scan"/"quick scan" → Quick Scan.
- "check" / "check my change" / anything else, optionally followed by a flow description → Check
  my change. Everything after the kind word is the flow text (optional — leave it off and the
  QA Lead writes scenarios from the diff instead; a flow still works with **no diff at all**,
  e.g. checking something already deployed).
- "mocked" or "real" anywhere in the text picks the run mode (default `mocked`).

## Steps

1. **Find the backend.** It's at `http://127.0.0.1:8400/api/v1` by default (`BE_PORT` in
   `run-local-dev.sh`); use `NEXT_PUBLIC_BACKEND_URL` from `frontend/.env.local` if that's been
   changed. Check it's up:
   ```bash
   curl -sf http://127.0.0.1:8400/api/v1/setup-check | head -c 1
   ```
   If that fails, the backend isn't running. Tell the developer to start it — don't start a
   long-running dev server yourself without asking:
   ```bash
   ./run-local-dev.sh   # from the repo root; starts backend (8400) + dashboard (4000)
   ```
   Offer to run it in the background if they'd rather not switch terminals.

2. **Start the run.** Pick the endpoint from `$ARGUMENTS` (see above):
   ```bash
   curl -s -X POST http://127.0.0.1:8400/api/v1/runs/quick-scan \
     -H 'content-type: application/json' -d '{"mode": "mocked"}'
   # or
   curl -s -X POST http://127.0.0.1:8400/api/v1/runs/check-change \
     -H 'content-type: application/json' \
     -d '{"mode": "mocked", "flow": "<the flow text, or omit the key entirely>"}'
   ```
   - `412` means a billed credential (`ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`) is set in the
     backend's environment — tell the developer to remove it from their shell profile and `.env`
     so Claude Code uses their subscription, then retry.
   - `409` means another run is already active — report its id (from `GET /api/v1/runs`) instead
     of starting a new one.
   Note the `id` from the response.

3. **Follow progress.** Poll until `status` is `finished` (every ~3s is plenty):
   ```bash
   curl -s http://127.0.0.1:8400/api/v1/runs/<id>
   ```
   While waiting, you can show the live log instead of polling blind:
   ```bash
   curl -s "http://127.0.0.1:8400/api/v1/runs/<id>/events?after=0"
   ```

4. **Report the result** directly in this conversation — don't just dump JSON:
   - The verdict (`PASS` / `FAILING` / `BLOCKED`) and `blocked_reason` if any.
   - `plan_summary` verbatim — this is where the test case scenarios the QA Lead planned show up,
     one per line, before the per-scenario results.
   - Each finding: severity, title, location, expected vs. actual.
   - The dashboard link for screenshots/traces, since those aren't in the terminal output:
     `http://127.0.0.1:4000/runs/<id>`.

## Rules

- Never pass an API key or bill the API on the developer's behalf — this skill only talks to the
  local backend, which itself refuses to run agents while a billed credential is set.
- Never start, stop, or modify anything in the app under test. This skill only calls the QA
  backend's own HTTP API.
- If `curl` isn't available, use the same requests via whatever HTTP client is at hand (`http`,
  `wget`, a short Python one-liner) — the contract is what matters, not the tool.
