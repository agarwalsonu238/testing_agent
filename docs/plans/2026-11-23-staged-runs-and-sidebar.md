# Plan: Truly staged runs (plan → review → approve → run → report) and a smaller sidebar

- **Date:** 2026-11-23
- **Status:** approved by the developer ("fix all the issues that are still not done")
- **Sides:** backend + frontend (contract change: additive fields only)
- **Follows:** `2026-11-21-four-stage-test-pipeline.md` (which left the frontend and the run order out of scope)

## Problems being fixed

1. The four roles ran, but interleaved: each executor was followed straight away by its reporter,
   and the run page showed everything at once. The run now goes through whole stages, one after
   the other.
2. Nothing paused for the developer to approve the reviewed test cases.
3. The sidebar listed QA Lead, test-case-reviewer, qa-reporter and Test writer as pages. They
   only run inside another flow; their pages just linked elsewhere.
4. Bug: after the first Functionality-tester call, its reporter marked every *other* Functionality
   case `skipped — "The agent did not report this case"` (it applied to all of the agent's
   planned cases, not just the ones in that call).

## Approach

### Backend
- `RunRecord` gains `stage` (`planning | reviewing | awaiting_approval | running | reporting |
  done`) and `activity` (one line, e.g. "Functionality tester · case 2 of 5"). `RunParams` gains
  `approve_plan`. `CheckChangeRequest` / `AgentRunRequest` gain `approve_plan: bool = False`.
- Approval gate: after the reviewed cases are stored, when `approve_plan` is set the run waits
  (`stage = awaiting_approval`). `POST /runs/{id}/approve` (body: `skip: [case ids]`) resumes it;
  skipped cases become `skipped`. Cancel still works while waiting.
- `run_review_agent` splits into `execute_agent` (executor only) and `report_agent` (reporter
  only). `qa_lead` executes **all** calls first (stage `running`), then writes **all** reports
  (stage `reporting`). Each executor's observations update its cases immediately; the reporter
  has the final say.
- `AgentCall.case_ids` scopes case updates to the cases in that call (fixes problem 4). A blocked
  executor marks its own cases `blocked` with the reason.
- `AgentInfo.standalone` (false for qa-lead, test-case-reviewer, qa-reporter, test-writer).

### Frontend
- Sidebar: only standalone agents, under "Run one agent". The pipeline-only agents' pages redirect
  to the flow that uses them.
- Run report: stage tabs follow `stage`; Review tab has the approve controls; Run tab is grouped
  agent by agent (waiting / running / done, with its cases); Report tab says when reports are
  still being written.
- Start forms: "Let me approve the test cases before they run" (on by default).

## Out of scope
- Running agents in parallel, editing case text before approving, any new dependency.

## Risks
- A run paused for approval holds the single run slot until approved or cancelled (the run page
  says so; Cancel is always available).
- Reporting after all executors means findings appear at the end rather than as each agent
  finishes. That is the requested behaviour.

## Test plan
- Backend: gate pauses/resumes/skips; cancel while paused; approve when not waiting → 409;
  executors all run before any reporter; case updates scoped to `case_ids`; blocked executor marks
  its cases; `standalone` flag; cancelled-request noise (done).
- Frontend: stage derivation from `stage`; approve controls; sidebar hides pipeline-only agents;
  start form sends `approve_plan`.
- Manual: a real run in the browser.
