"""Check my change: the QA Lead (Writer) plans test cases, a Reviewer tightens or rejects them,
then the right agents execute them and a Reporter writes up each one's findings.

Which review agents run is a fixed rule (plan section 2): UI files → Design reviewer, logic/API
files → API checker, every change → Code reviewer. The QA Lead is the only agent that ever sees
the diff or the flow text; it writes a self-contained test case for every agent that will run.
The Reviewer then tightens or rejects each draft case before anything is stored or executed.
Every executor (Functionality tester, API checker, Code reviewer, Design reviewer) works only
from its assigned case(s) and reports facts; a Reporter turns those facts into the polished
finding. Cases are planned whenever there's a diff or a developer-described flow to test, even
when there's no diff at all: a flow to test is never silently skipped just because nothing
changed in the repo.
"""

import asyncio
import json
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from pydantic import ValidationError

from app.core.errors import BlockedError, PreconditionError
from app.integrations import git
from app.schemas.qa_config import ChangeRules
from app.schemas.runs import RunMode, TestCase
from app.services.agents import (
    API_CHECKER,
    CODE_REVIEWER,
    DESIGN_REVIEWER,
    FUNCTIONALITY_TESTER,
    LEAD_SCHEMA,
    QA_LEAD,
    REVIEW_SCHEMA,
    TEST_CASE_REVIEWER,
    AgentCall,
    AgentDeps,
    LeadPlan,
    PendingReport,
    PlannedCase,
    ReviewedCase,
    ReviewResult,
    copy_designs,
    execute_agent,
    get_agent,
    invoke_agent,
    report_agent,
)
from app.services.api_reference import agent_notes, build_references
from app.services.run_manager import RunContext

MAX_DESIGN_ROUTES = 3
MAX_LISTED_FILES = 200


def _matches(path: str, patterns: list[str]) -> bool:
    candidates = (path, f"/{path}")
    return any(fnmatchcase(c, p) for c in candidates for p in patterns)


@dataclass
class ChangeSummary:
    files: list[str]
    ui: list[str]
    logic: list[str]
    other: list[str]

    @property
    def agents(self) -> list[str]:
        """Review agents the fixed rule requires for this diff, in run order.

        The Functionality tester isn't decided here: it runs whenever there are test case
        scenarios to try, which can happen with or without a diff (see `run_check_change`).
        """
        if not self.files:
            return []
        needed = [CODE_REVIEWER]
        if self.ui:
            needed.append(DESIGN_REVIEWER)
        if self.logic:
            needed.append(API_CHECKER)
        return needed


def classify_changes(files: list[str], rules: ChangeRules) -> ChangeSummary:
    """Sort changed files into UI, logic and other (ignored files are dropped)."""
    kept = [f for f in files if not _matches(f, rules.ignore)]
    ui = [f for f in kept if _matches(f, rules.ui)]
    logic = [f for f in kept if _matches(f, rules.logic)]
    other = [f for f in kept if f not in ui and f not in logic]
    return ChangeSummary(files=kept, ui=ui, logic=logic, other=other)


def _file_list(title: str, files: list[str]) -> list[str]:
    shown = files[:MAX_LISTED_FILES]
    more = len(files) - len(shown)
    return [f"{title}:"] + [f"  - {f}" for f in shown] + ([f"  - … {more} more"] if more else [])


async def run_check_change(
    ctx: RunContext, deps: AgentDeps, *, mode: RunMode, base_ref: str | None, flow: str | None
) -> None:
    s = deps.settings
    repo = s.app_repo_path
    if repo is None or not await git.is_repo(repo):
        raise PreconditionError("APP_REPO_PATH must point at the app's git repository")
    base = base_ref or s.diff_base
    since = await git.merge_base(repo, base)
    if since is None:
        ctx.event(f"'{base}' not found; checking uncommitted changes only", level="warn")
        since = "HEAD"
    files = await git.changed_files(repo, since)
    summary = classify_changes(files, deps.qa.changes)

    if not summary.files and not flow:
        ctx.record.plan_summary = f"No changes since {base}; nothing to check."
        ctx.save()
        return

    changes: list[str] = []
    if summary.files:
        patch = await git.diff(repo, since)
        diff_path = ctx.dir / "diff.patch"
        await asyncio.to_thread(diff_path.write_text, patch)
        ctx.add_artifact("Diff", diff_path, "code")
        changes = [
            "",
            "## Change under review",
            f"- Diff against {base} ({since[:12]}): {diff_path} (read it with the Read tool)",
            *_file_list("- UI files", summary.ui),
            *_file_list("- Logic/API files", summary.logic),
            *_file_list("- Other files", summary.other),
        ]
        ctx.event(
            f"{len(summary.files)} changed file(s): {len(summary.ui)} UI, "
            f"{len(summary.logic)} logic"
        )
    else:
        # A flow was given but nothing changed in the repo (e.g. testing an already-deployed
        # change against a live app): still plan and run the scenarios for it.
        ctx.event(f"No changes since {base}; testing the described flow only", level="warn")

    review_agents = summary.agents  # Code reviewer / Design reviewer; functionality runs below
    ctx.set_stage("planning", "The QA Lead is writing the test cases")
    plan = await _lead_plan(
        ctx, deps, mode=mode, changes=changes, flow_hint=flow, required_agents=review_agents
    )
    ctx.set_stage("reviewing", "The test case reviewer is checking the cases")
    reviewed = await _review_cases(ctx, deps, mode, plan.test_cases)
    store_test_cases(ctx, plan, reviewed, FUNCTIONALITY_TESTER, [flow] if flow else [])

    lines = [plan.summary.strip()] if plan.summary.strip() else []
    if ctx.record.test_cases:
        lines.append(f"Test cases ({len(ctx.record.test_cases)}), planned before testing:")
        lines += [f"  {c.id} [{c.agent}] {c.title}" for c in ctx.record.test_cases]
    if review_agents:
        lines.append("Also reviewing: " + ", ".join(review_agents))
    ctx.record.plan_summary = "\n".join(lines)
    ctx.save()

    await _approval_gate(ctx)

    # Functionality is always checked first: every case is planned and reviewed before anything
    # runs, and every functionality case is tested before the (slower, less important) code,
    # design and API review.
    s = deps.settings
    calls: list[AgentCall] = []
    func_cases = _cases_for(ctx, FUNCTIONALITY_TESTER)
    for i, case in enumerate(func_cases, 1):
        calls.append(
            AgentCall(
                agent=get_agent(s, FUNCTIONALITY_TESTER),
                task=f"Test case {i} of {len(func_cases)}:\n{case_text(case)}",
                context=cases_context([case]),
                mode=mode,
                case_ids=[case.id],
                # Distinct evidence folder per case: without it, case 2's screenshots and
                # recorder log would overwrite case 1's.
                work_dir_name=f"{FUNCTIONALITY_TESTER}-{i}",
            )
        )
    for name in review_agents:
        cases = _cases_for(ctx, name)
        if not cases:
            ctx.event(f"{name} skipped: no approved test case for it", level="warn", source=name)
            continue
        if name == CODE_REVIEWER:
            calls.append(
                AgentCall(
                    agent=get_agent(s, name),
                    task="Review this change against the repo's guidelines and skills.",
                    mode=mode,
                    context=cases_context(cases),
                    case_ids=[c.id for c in cases],
                )
            )
        elif name == DESIGN_REVIEWER:
            calls += _design_calls(ctx, deps, mode, plan.design_routes, cases)
        elif name == API_CHECKER:
            calls.append(
                AgentCall(
                    agent=get_agent(s, name),
                    task="Compare the frontend's API calls with the backend's routes for this "
                    "change.",
                    mode=mode,
                    context=cases_context(cases),
                    case_ids=[c.id for c in cases],
                )
            )
    if not calls:
        raise BlockedError("No approved test case is left to run")
    await _execute_then_report(ctx, deps, calls)


async def _approval_gate(ctx: RunContext) -> None:
    """When the developer asked for it, pause until they approve the reviewed test cases.

    Cases they skip are never run. Cancel still works while the run waits.
    """
    runnable = [c for c in ctx.record.test_cases if c.status == "planned"]
    if not ctx.record.params.approve_plan or not runnable:
        return
    skipped = await ctx.wait_for_approval()
    skipped_now = [c for c in runnable if c.id.upper() in skipped]
    for case in skipped_now:
        case.status, case.note = "skipped", "You chose not to run this case"
    ctx.save()
    ctx.event(
        f"Approved: {len(runnable) - len(skipped_now)} case(s) will run, "
        f"{len(skipped_now)} skipped by you",
        source=QA_LEAD,
    )


def _activity(call: AgentCall, index: int, total: int) -> str:
    return f"{call.agent.name} · {index} of {total}: {_first_line(call.task)[:90]}"


async def _execute_then_report(ctx: RunContext, deps: AgentDeps, calls: list[AgentCall]) -> None:
    """Stage 3 runs every executor, one at a time; only then does stage 4 write each report."""
    pending: list[PendingReport] = []
    for i, call in enumerate(calls, 1):
        ctx.set_stage("running", _activity(call, i, len(calls)))
        outcome = await execute_agent(ctx, deps, call)
        if isinstance(outcome, PendingReport):
            pending.append(outcome)
    for i, item in enumerate(pending, 1):
        ctx.set_stage("reporting", f"Writing report {i} of {len(pending)}: {item.call.agent.name}")
        await report_agent(ctx, deps, item)


async def _review_cases(
    ctx: RunContext, deps: AgentDeps, mode: RunMode, drafts: list[PlannedCase]
) -> list[ReviewedCase]:
    """Have the Reviewer tighten or reject each draft case before anything is stored or run.

    The Reviewer never sees the diff or the flow text — only the cases themselves. Falls back to
    the drafts, unreviewed, when the Reviewer gives no usable reply.
    """
    as_written = [
        ReviewedCase(title=c.title, agent=c.agent, steps=c.steps, expected=c.expected)
        for c in drafts
    ]
    if not drafts:
        return as_written
    run = await invoke_agent(
        ctx,
        deps,
        AgentCall(
            agent=get_agent(deps.settings, TEST_CASE_REVIEWER),
            task="Review these draft test cases before anything is tested.",
            mode=mode,
            context=[
                "",
                "## Draft test cases",
                json.dumps([c.model_dump() for c in drafts]),
            ],
            schema=REVIEW_SCHEMA,
        ),
    )
    if not run.result.ok or run.result.structured is None:
        ctx.event(
            f"Test case reviewer gave no result ({run.result.error or 'no JSON reply'}); using "
            "the drafts as written",
            level="warn",
        )
        return as_written
    try:
        result = ReviewResult.model_validate(run.result.structured)
    except ValidationError:
        ctx.event(
            "Test case reviewer's reply didn't match the format; using the drafts as written",
            level="warn",
        )
        return as_written
    if len(result.cases) != len(drafts):
        ctx.event(
            "Test case reviewer returned a different number of cases; using the drafts as written",
            level="warn",
        )
        return as_written
    changed = sum(1 for c in result.cases if c.review_status != "approved")
    ctx.event(
        f"Test case reviewer: {changed} of {len(result.cases)} case(s) changed",
        source=TEST_CASE_REVIEWER,
    )
    return result.cases


def store_test_cases(
    ctx: RunContext,
    plan: LeadPlan,
    reviewed: list[ReviewedCase],
    fallback_agent: str,
    fallback: list[str],
) -> None:
    """Save the reviewed test cases on the run and in `test-cases.json` (before anything runs).

    A rejected case is stored `skipped` with the reviewer's reason as its note, and is never
    handed to an executor (see `_cases_for`).
    """
    cases: list[TestCase] = []
    for rc in reviewed:
        agent = rc.agent if rc.agent in _CASE_AGENTS else fallback_agent
        rejected = rc.review_status == "rejected"
        cases.append(
            TestCase(
                id=f"TC-{len(cases) + 1}",
                title=rc.title.strip()[:200] or "Untitled case",
                agent=agent,
                steps=[x.strip() for x in rc.steps if x.strip()],
                expected=rc.expected.strip(),
                status="skipped" if rejected else "planned",
                note=rc.review_note if rejected else None,
                review_note=None if rejected else rc.review_note,
                review_status=rc.review_status,
            )
        )
    if not cases:  # the lead gave no structured cases: the older free-text scenarios
        for text in plan.scenarios or fallback:
            cases.append(
                TestCase(
                    id=f"TC-{len(cases) + 1}",
                    title=_first_line(text),
                    agent=fallback_agent,
                    steps=[text],
                )
            )
    ctx.record.test_cases = cases
    path = ctx.dir / "test-cases.json"
    path.write_text(json.dumps([c.model_dump() for c in cases], indent=2))
    ctx.add_artifact("Test cases (planned first)", path, "log")
    ctx.event(f"{len(cases)} test case(s) planned and saved before testing", source=QA_LEAD)
    ctx.save()


def case_text(case: TestCase) -> str:
    steps = "\n".join(f"  {i}. {x}" for i, x in enumerate(case.steps, 1))
    return f"{case.id}: {case.title}\n{steps}\nExpected: {case.expected}".strip()


def cases_context(cases: list[TestCase]) -> list[str]:
    if not cases:
        return []
    return [
        "",
        "## Planned test cases (written before testing: execute exactly these)",
        *[case_text(c) for c in cases],
        "Every case above needs a result in your reply: pass, fail, blocked or skipped, with a "
        "one-line note of what you observed. A case passes only if its Expected result was "
        "actually observed.",
    ]


_CASE_AGENTS = {FUNCTIONALITY_TESTER, API_CHECKER, CODE_REVIEWER, DESIGN_REVIEWER}


def _cases_for(ctx: RunContext, agent: str) -> list[TestCase]:
    """This agent's cases that are actually runnable — a case the Reviewer rejected is `skipped`
    from the start and never reaches an executor."""
    return [c for c in ctx.record.test_cases if c.agent == agent and c.status == "planned"]


def _first_line(text: str) -> str:
    for line in text.strip().splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return "(empty)"


async def _lead_plan(
    ctx: RunContext,
    deps: AgentDeps,
    *,
    mode: RunMode,
    changes: list[str],
    flow_hint: str | None,
    target_agent: str | None = None,
    required_agents: list[str] | None = None,
) -> LeadPlan:
    if target_agent:
        ask = (
            f"Write ALL the test cases for this request first, before anything is tested. The "
            f"{target_agent} will execute them, so set every case's agent to {target_agent}. "
            "Cover the normal path, then edge, empty, invalid-input and failure cases (for an "
            "API: each status code, filters, pagination, bad parameters, auth). Each case has a "
            "title, numbered steps and an Expected result. Leave design_routes empty. "
            f"{target_agent} runs no matter what you write, so write at least one case for it "
            "even if you find nothing wrong — a case confirming the safe behavior beats none."
        )
    elif changes:
        required = ", ".join(required_agents or [CODE_REVIEWER])
        ask = (
            "Plan the checks for this change: list the routes whose UI changed (for "
            "design_routes), then write a self-contained test case for every agent that will "
            "run — the normal path first, then the important edge cases the change implies. "
            f"These agents run no matter what you write, so you must write at least one case "
            f"for each of them even if you find nothing wrong: {required}. A case confirming "
            "the safe behavior (name the file/route/endpoint and what should still be true of "
            "it) beats leaving that agent with nothing to check."
        )
    else:
        ask = (
            "There is no local code diff to check — only a flow the developer wants tested in "
            "the running app. Turn it into 1-4 concrete test cases for the Functionality tester: "
            "the normal path first, then the important edge cases it implies. Leave "
            "design_routes empty."
        )
    context = list(changes)
    if flow_hint:
        ask += (
            " The developer specifically asked to test this, including any edge cases they "
            "named — make sure your scenarios cover it:"
        )
        context += ["", "## Flow the developer asked to test", flow_hint]
    try:
        run = await invoke_agent(
            ctx,
            deps,
            AgentCall(
                agent=get_agent(deps.settings, QA_LEAD),
                task=ask,
                mode=mode,
                context=context,
                schema=LEAD_SCHEMA,
                # The Writer is the only role allowed to see diff.patch; every other call in
                # this run gets a narrower (usually empty) add_dirs.
                add_dirs=[ctx.dir],
            ),
        )
        if run.result.ok and run.result.structured is not None:
            plan = LeadPlan.model_validate(run.result.structured)
            ctx.event(f"QA Lead: {plan.summary[:300]}", source=QA_LEAD)
            return plan
        ctx.event(f"QA Lead gave no plan: {run.result.error or 'no JSON reply'}", level="warn")
    except ValidationError:
        ctx.event("QA Lead's plan didn't match the format; using the fixed rule only", level="warn")
    except BlockedError:
        raise
    return LeadPlan()


def _design_calls(
    ctx: RunContext, deps: AgentDeps, mode: RunMode, routes: list[str], cases: list[TestCase]
) -> list[AgentCall]:
    s = deps.settings
    clean = [r for r in dict.fromkeys(routes) if r.startswith("/")][:MAX_DESIGN_ROUTES]
    if not clean:
        ctx.event("Design reviewer skipped: the QA Lead found no changed route", level="warn")
        return []
    calls: list[AgentCall] = []
    for route in clean:
        designs = copy_designs(s, route, ctx.dir)
        if not designs and not s.figma_mcp_url:
            ctx.event(
                f"Design reviewer skipped {route}: no design PNG in {s.designs_dir}", level="warn"
            )
            continue
        call = design_call(deps, route, mode, designs)
        call.context += cases_context(cases)
        call.case_ids = [c.id for c in cases]
        calls.append(call)
    return calls


def design_call(
    deps: AgentDeps,
    route: str,
    mode: RunMode,
    designs: dict[str, Path],
) -> AgentCall:
    s = deps.settings
    url = f"{s.app_url.rstrip('/')}{route}"
    design_lines = [f"- Design ({v}): {p}" for v, p in designs.items()] or [
        "- No PNG for this route: use the Figma MCP server to get the design frame."
    ]
    # The design-reviewer needs Read access to its copied design PNG(s), nothing else from the
    # run folder — never the diff, which lives in the run folder's root.
    add_dirs = list({p.parent for p in designs.values()})
    if s.designs_dir.is_dir():
        add_dirs.append(s.designs_dir.resolve())
    return AgentCall(
        agent=get_agent(deps.settings, DESIGN_REVIEWER),
        task=f"Compare {url} with its design at desktop (1440x900) and mobile (390x844) size.",
        mode=mode,
        route=route,
        designs=designs,
        context=["", "## Designs", *design_lines],
        add_dirs=add_dirs,
    )


async def run_single_agent(
    ctx: RunContext, deps: AgentDeps, *, agent: str, task: str, route: str | None, mode: RunMode
) -> None:
    """Run one agent on demand (e.g. Design reviewer on /pricing)."""
    s = deps.settings
    if agent in (QA_LEAD, "test-writer"):
        raise PreconditionError(f"{agent} runs from Check my change / Save as test, not on its own")

    # Any local diff goes to the Writer (below), never straight to the executor: the Writer is
    # the only role allowed to read it, and turns what matters into the case it writes.
    changes: list[str] = []
    if agent in (CODE_REVIEWER, API_CHECKER):
        repo = s.app_repo_path
        has_repo = repo is not None and await git.is_repo(repo)
        if not has_repo and agent == CODE_REVIEWER:
            raise PreconditionError("APP_REPO_PATH must point at the app's git repository")
        if has_repo and repo is not None:
            since = await git.merge_base(repo, s.diff_base) or "HEAD"
            diff_path = ctx.dir / "diff.patch"
            await asyncio.to_thread(diff_path.write_text, await git.diff(repo, since))
            ctx.add_artifact("Diff", diff_path, "code")
            changes = ["", "## Change under review", f"- Diff against {s.diff_base}: {diff_path}"]
        elif agent == API_CHECKER:
            # The API checker can test a pasted endpoint live without any local checkout.
            changes = ["", "No local repository is configured: test the endpoint live only."]

    # Always first: turn the developer's prompt (and any diff) into a full list of test cases,
    # review them, store the result, and only then let the agent execute them.
    ctx.event(f"Planning test cases for {agent} before testing", source=QA_LEAD)
    ctx.set_stage("planning", "The QA Lead is writing the test cases")
    plan = await _lead_plan(
        ctx, deps, mode=mode, changes=changes, flow_hint=task, target_agent=agent
    )
    ctx.set_stage("reviewing", "The test case reviewer is checking the cases")
    reviewed = await _review_cases(ctx, deps, mode, plan.test_cases)
    store_test_cases(ctx, plan, reviewed, agent, [task])
    ctx.record.plan_summary = plan.summary.strip() or None
    ctx.save()
    await _approval_gate(ctx)
    approved = _cases_for(ctx, agent)
    if not approved:
        raise BlockedError("No approved test case is left to run")
    cases = cases_context(approved)
    if agent == DESIGN_REVIEWER:
        if not route:
            raise PreconditionError("The Design reviewer needs a route, e.g. /pricing")
        designs = copy_designs(s, route, ctx.dir)
        if not designs and not s.figma_mcp_url:
            raise PreconditionError(
                f"No design PNG for {route} in {s.designs_dir} and no Figma MCP"
            )
        call = design_call(deps, route, mode, designs)
        call.task = f"{call.task}\n{task}"
        call.context += cases
    elif agent in (CODE_REVIEWER, API_CHECKER):
        context: list[str] = []
        if agent == API_CHECKER:
            refs = await build_references(task, deps.probe, ctx.dir)
            if refs:
                ctx.record.api_references.extend(refs)
                ctx.save()
                context += [
                    "",
                    "## Already measured by the QA backend (exact, shown on the report page)",
                    "The run page already lists every key with its type and which common "
                    "parameters changed the response, so do NOT repeat key tables or re-test "
                    "those parameters. Your job: a short plain-language answer to the task, "
                    "check the code if it is available, and report real problems only.",
                    *agent_notes(refs),
                ]
        call = AgentCall(agent=get_agent(s, agent), task=task, mode=mode, context=context + cases)
    else:
        call = AgentCall(
            agent=get_agent(s, agent), task=task, mode=mode, route=route, context=cases
        )
    call.case_ids = [c.id for c in approved]
    await _execute_then_report(ctx, deps, [call])
