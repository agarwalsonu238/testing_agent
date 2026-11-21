# Plan: Four-stage test pipeline (write → review → execute → report)

- **Date:** 2026-11-21
- **Status:** approved
- **Sides:** backend only (no frontend/API contract changes)
- **Ticket / request:** split the single "plan + execute" agent into four isolated roles; only the
  first one may see the requirement (diff / flow text)

## Goal

Replace today's shape — one agent (QA Lead) plans test cases, then each reviewing agent both
*executes* its assigned cases *and* writes its own findings/report — with four strictly separated
roles per `backend/qa/agents/*.md`:

1. **Writer** (`qa-lead`, existing) — the only role that sees the diff/flow. Writes test cases for
   every agent that will run.
2. **Reviewer** (`test-case-reviewer`, new) — sees only the draft test cases. Tightens vague steps
   or an unfalsifiable `expected` line into something concrete; rejects a case it cannot fix
   without inventing facts. Never sees the diff/flow.
3. **Executor** (`functionality-tester`, `api-checker`, `code-reviewer`, `design-reviewer` —
   behavior narrowed) — sees only the reviewed test case(s) assigned to it, plus its normal tools
   (browser, repo read, live HTTP). Executes exactly what the case says and reports **facts only**
   — no severity, no category, no polished summary. Never sees the diff/flow.
4. **Reporter** (`qa-reporter`, new) — sees only the test cases and the executor's factual output
   for that same call. Turns facts into the polished `AgentReport` (summary, findings with
   severity/category/suggested fix, `case_results`) in the existing plain-language style. Never
   sees the diff/flow.

- [ ] `test-case-reviewer` and `qa-reporter` agent definitions exist in `backend/qa/agents/`
- [ ] `qa-lead` writes self-contained cases for all four executor agents, not just the Functionality
      tester + a free-text `code_review_focus` hint
- [ ] Every executor agent's prompt and output schema stop requiring/producing `findings`/`summary`
      — they report observed facts and evidence only
- [ ] No executor, reviewer, or reporter call can read `diff.patch` or receives the flow text —
      verified by actual tool/dir permissions, not just prompt wording
- [ ] `/api/v1` response shapes (`RunDetail`, `AgentResult`, `Finding`) are unchanged; frontend
      needs no changes
- [ ] Existing quality gates (`ruff format/check`, `mypy`, `pytest`) pass

## Out of scope

- Any frontend change. The external contract (`RunDetail`, `AgentResult`, `Finding`, `TestCase`)
  stays byte-for-byte compatible; this is an internal backend pipeline change only.
- Quick Scan (no agents involved) and the Test writer agent (operates on a passing run's evidence,
  not on test cases).
- Changing how `api-checker` Mode A/B are *selected* — only how it reports once running.
- Optimizing call count/latency beyond what's described below (see Open questions).

## Decisions already made

| Question | Answer |
|---|---|
| Which agents go through the 4-stage pipeline? | All of them: functionality-tester, api-checker, code-reviewer, design-reviewer |
| What does the reviewer do with a vague/untestable case? | Rewrite it to be concrete; only reject outright if that's impossible without new facts |

Taking "all of them" seriously has one real consequence worth flagging up front: **code-reviewer's
entire method today is "read the diff, then hunt for bugs."** Cut off from the diff, it can only
verify what the Writer already thought to ask about — it stops being an independent bug-hunter and
becomes a checklist-verifier. See **Risks** below for the mitigation this plan proposes.

## Approach

### 1. Writer (`qa-lead.md`) — modified

Today it writes 1-4 scenarios for the Functionality tester plus a one-line
`code_review_focus` hint and a bare `design_routes` list; `code-reviewer`/`design-reviewer`/
`api-checker` then read the diff themselves. Change it to write **every** case for **every**
agent in the same self-contained `title / steps / expected` shape, detailed enough that the
executor — which will never see the diff — can act on it alone:

- `functionality-tester` cases: unchanged (already self-contained UI flows).
- `design-reviewer` cases: name the route, viewport(s), and which specific visual aspect to check
  (already close to today; just becomes an explicit case instead of a bare route list).
- `api-checker` cases: name the method+path and the exact field/behavior to confirm by reading the
  *current* frontend/backend source — this replaces today's "Mode B" free-form diff comparison;
  the Writer (who read the diff) already knows which field/endpoint is suspect, so it can name it.
- `code-reviewer` cases: name the file:line and quote the specific new/changed lines plus what
  could be wrong about them (e.g. "checkout.py:142 added `if amount <= 0: raise ValueError` —
  confirm this path is actually reached when amount is 0 and that the caller catches it"). The
  quoted snippet is the sanctioned hand-off of "what changed," scoped to one concern at a time —
  the Writer never hands over the full diff or any narrative about *why*.

`LeadPlan`/`LEAD_SCHEMA` (`agents.py`) gains richer per-case detail but keeps the same
`title/agent/steps/expected` shape — no new top-level fields needed. `code_review_focus` and the
bare `design_routes`-only flow are retired in favor of full cases; `design_routes` itself is kept
only as the mechanical "which PNGs to copy into the run folder" list, not as review guidance.

### 2. Reviewer (`test-case-reviewer.md`) — new

- **Tools: none.** No Read/Glob/Grep/MCP — it only sees the JSON case list in its prompt, so there
  is nothing on disk for it to over-reach into even by accident.
- Input: the Writer's draft cases (title, agent, steps, expected) — nothing else.
- Checks per case: steps are concrete actions (not "make sure it works"); `expected` is a single
  observable/falsifiable condition; the case doesn't ask for a prohibited action (payment,
  transfer, deletion, account change); the case's shape matches its assigned agent (a
  `code-reviewer` case names a file; a `functionality-tester` case is a numbered UI flow; etc.).
- Output: the same cases, each either `approved` (unchanged), `rewritten` (tightened wording, same
  intent), or `rejected` (with a one-line reason) when it can't be fixed without new facts a
  reviewer isn't allowed to invent.
- New schema in `agents.py`: `ReviewedCase` (`title, agent, steps, expected, review_status,
  review_note`) and `REVIEW_SCHEMA`. New `TEST_CASE_REVIEWER` agent-name constant.
- Orchestration (`qa_lead.py`): one call right after `_lead_plan`, before `store_test_cases`.
  Rejected cases are stored with `status="skipped"` and the rejection reason as `note`, and are
  never handed to an executor. `TestCase` (`schemas/runs.py`) gains an optional `review_note: str
  | None` field (additive, backward compatible) so the stored `test-cases.json` artifact shows
  what the reviewer changed, even with no frontend change.

### 3. Executors — behavior narrowed, not rewritten

Each keeps its existing tools/MCP servers and keeps *acting* the same way (Playwright steps, live
HTTP calls, reading the named file, rendering the route). What changes is what they're told and
what they report:

- They receive the reviewed test case(s) assigned to them and **never** the diff, the flow text,
  or `design_routes`/`code_review_focus` narrative context. Concretely: stop passing `changes`
  (the diff context block) into any executor's `AgentCall.context` in `qa_lead.py` — today
  `code-reviewer`, `design-reviewer`, and `api-checker` all receive it.
- They stop authoring `findings`/`summary`. New shared schema `ExecutionRecord`
  (`steps`, `case_observations: [{id, status, observed, evidence}]`) and `EXECUTION_SCHEMA`
  replace `AgentReport`/`REPORT_SCHEMA` as *their* reply contract. `observed` is a plain factual
  statement ("the function returns before the catch block runs"; "response has 12 items, design
  shows the gap as 16px, measured gap is 4px") — explicitly no severity/category/fix.
- `functionality-tester` specifically: the deterministic Playwright-log verdict machinery
  (`checks_from_tool_calls`, `checks_from_recording`, `flow_verdict`) is unchanged — it already
  never trusted the model's own words for pass/fail, and that invariant must be preserved. The
  executor's JSON reply only needs `steps` + evidence; the code-computed `checks` list travels
  forward to the Reporter alongside it as ground truth.
- design-reviewer/code-reviewer/api-checker narrow from "report every difference/bug you notice"
  to "report what you observed for each assigned case" — they stop free-ranging across the whole
  diff/page and only speak to what the case asked.

### 4. Reporter (`qa-reporter.md`) — new

- **Tools: none** — same reasoning as the Reviewer.
- Input, per executor call: that call's test case(s), its `ExecutionRecord`, and (for
  Functionality tester only) the code-computed `checks` list. Never the diff/flow.
- Output: today's `AgentReport` shape unchanged (`summary`, `findings`, `case_results`, `steps`)
  — same `REPORT_SCHEMA`, same plain-language writing rules (`_WRITING_RULES`). It turns "the
  measured gap is 4px, design shows 16px" into a finding with severity/category/suggested fix,
  same as an executor does today — the only change is *which agent* writes that prose, and that it
  does so from a smaller, factual input instead of free exploration.
- Orchestration: `run_review_agent` becomes a two-call sequence per existing call site — invoke the
  executor, get its `ExecutionRecord`, invoke the Reporter with that record, parse the resulting
  `AgentReport` exactly as `run_review_agent` does today (findings → `ctx.add_findings`,
  `case_results` → `_apply_case_results`, steps/screenshots → artifacts). One Reporter call per
  existing executor call (not one global end-of-run call) — see Open questions for the tradeoff.

### Suggested build order (incremental, testable at each step)

1. Reviewer + Writer changes (stages 1-2) — land and verify `test-cases.json` output looks right
   on a real run before touching execution.
2. Reporter + `ExecutionRecord` split, starting with `functionality-tester` only (smallest,
   already closest to factual reporting today).
3. Extend the Executor/Reporter split to `api-checker`, then `code-reviewer` and `design-reviewer`.

## File impact map

| File | Change |
|---|---|
| `backend/qa/agents/test-case-reviewer.md` | add |
| `backend/qa/agents/qa-reporter.md` | add |
| `backend/qa/agents/qa-lead.md` | modify — write full per-agent cases, not just Functionality scenarios + a focus hint |
| `backend/qa/agents/functionality-tester.md` | modify — report `ExecutionRecord` facts, not `findings` |
| `backend/qa/agents/api-checker.md` | modify — same; Mode B becomes case-driven, no direct diff reading |
| `backend/qa/agents/code-reviewer.md` | modify — same; works from the quoted snippet in its case, not a diff file |
| `backend/qa/agents/design-reviewer.md` | modify — same; scoped to assigned cases, not a free top-to-bottom pass |
| `backend/src/app/services/agents.py` | add `ReviewedCase`, `REVIEW_SCHEMA`, `ExecutionRecord`, `EXECUTION_SCHEMA`, `TEST_CASE_REVIEWER`/`QA_REPORTER` constants; split `invoke_agent`/`run_review_agent` into executor-call + reporter-call; stop building `changes` into executor `AgentCall.context` |
| `backend/src/app/services/qa_lead.py` | add the Reviewer call between `_lead_plan` and `store_test_cases`; stop passing `changes` to code-reviewer/design-reviewer/api-checker calls; retire `code_review_focus` free-text path |
| `backend/src/app/schemas/runs.py` | add `TestCase.review_note: str \| None = None` (additive) |
| `backend/tests/` | new/updated unit tests (see Test plan) |

No changes to `backend/src/app/api/routes/`, `frontend/`, or any response model's required fields.

## Data / state delta

- `TestCase` gains one optional field (`review_note`). Existing stored runs without it still parse
  (default `None`).
- No new persisted entities, no migrations (no DB in this project).
- Run folder gains no new files; `agent-output/<agent>/` still holds the same evidence. The
  Reporter call's own Claude stream log can be written alongside the executor's in the same work
  dir (e.g. `claude-stream.reporter.jsonl`) purely for debugging — not required by the contract.

## Risks & tradeoffs

- **Code review loses serendipitous bug-finding.** Today it reads the whole diff and can flag
  anything; under strict isolation it only verifies what the Writer thought to ask about. The
  mitigation above (Writer quotes the specific changed lines into each case) keeps real code
  visible to the reviewer without handing over the diff or the "why" — but it's a genuine behavior
  change, not a pure refactor. Worth a deliberate before/after comparison on a real diff during
  Build before calling this done.
- **Filesystem isolation must be real, not just prompt-level.** `diff.patch` lives in `ctx.dir`,
  and `ctx.dir` is in `add_dirs` for every agent today (so evidence/screenshots are reachable).
  Removing diff *mentions* from an executor's prompt does nothing if it still has `Glob`/`Grep` on
  a directory containing `diff.patch`. Build must verify (e.g. with a test that asserts an
  executor's permission rules/`add_dirs` cannot resolve to `diff.patch`) that this is actually
  blocked, not just unprompted.
- **More Claude Code calls per run → more latency/time.** Today: 1 (Writer) + one call per
  executor invocation. New: +1 (Reviewer, once per run) + 1 Reporter call per existing executor
  call — roughly doubles the number of `claude -p` subprocess calls for Check my change. Each call
  is a real subprocess with its own startup cost. Mitigated partly by giving the Reviewer and
  Reporter no tools/MCP (fastest possible calls) and optionally a cheaper `model:` override
  (`AgentDefinition.model` already supports this) since neither does tool-calling, only structured
  text transformation.
- **Design-reviewer and api-checker narrow their coverage.** Both currently free-range (design
  reviewer checks top-to-bottom; api-checker's Mode B inspects the whole contract) and under this
  plan only speak to assigned cases. If the Writer misses something, nothing downstream catches it
  — by design, since only the Writer sees the requirement. This is the direct, intended
  consequence of "only agent 1 knows the requirement"; flagging it so it's a deliberate trade, not
  a surprise regression.

## Approval needed for

- No new dependencies.
- No API/contract changes requiring frontend coordination.
- The code-reviewer mitigation above (quoting changed lines into a case instead of handing over
  the diff) is this plan's proposed way to satisfy "agent 2+ never sees the requirement" while
  keeping code review useful — confirm this reading is acceptable before Build starts on that
  agent specifically.

## Test plan

- Backend unit (`backend/tests/unit/`):
  - `test_case_reviewer` schema round-trip: approved/rewritten/rejected cases map to the right
    `TestCase.status`/`review_note`.
  - Rejected cases never reach an executor (orchestration test on `run_check_change` with a mocked
    Reviewer reply containing a rejection).
  - `ExecutionRecord` → `AgentReport` hand-off: Reporter call receives exactly the executor's
    record + case list and nothing else (assert the built prompt contains no diff path, no flow
    text, for each of the four executor agents).
  - Functionality tester: existing `flow_verdict`/`checks_from_recording` tests still pass
    unchanged (invariant preserved).
  - Permission/`add_dirs` test: an executor or Reporter/Reviewer call cannot resolve a path to
    `diff.patch` (the filesystem-isolation risk above).
- Backend API (`backend/tests/`): `POST /runs/check-change` end-to-end with a fake `ClaudeCode`
  that returns canned Reviewer/Executor/Reporter replies — assert `RunDetail` shape is unchanged
  from today's contract (same fields, same `Finding`/`AgentResult` shape).
- Manual: run `./run-local-dev.sh`, trigger Check my change against a real small diff, read
  `test-cases.json` and `agent-output/*/claude-stream*.jsonl` in the run folder to confirm no
  executor/reporter/reviewer prompt contains diff content or flow text, and that the final report
  still reads the same as before to a non-technical reader.
