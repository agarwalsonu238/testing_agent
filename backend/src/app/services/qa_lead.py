"""Check my change: the QA Lead plans test case scenarios, then the right agents run them.

Which review agents run is a fixed rule (plan section 2): UI files → Design reviewer, logic/API
files → API checker, every change → Code reviewer. The QA Lead agent adds the details the rule
can't: which routes changed, what the code review should focus on, and — always the first thing
that runs — a numbered list of test case scenarios (the normal path plus edge cases) for the
Functionality tester. Scenarios are planned whenever there's a diff or a developer-described
flow to test, even when there's no diff at all: a flow to test is never silently skipped just
because nothing changed in the repo.
"""

import asyncio
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from pydantic import ValidationError

from app.core.errors import BlockedError, PreconditionError
from app.integrations import git
from app.schemas.qa_config import ChangeRules
from app.schemas.runs import RunMode
from app.services.agents import (
    API_CHECKER,
    CODE_REVIEWER,
    DESIGN_REVIEWER,
    FUNCTIONALITY_TESTER,
    LEAD_SCHEMA,
    QA_LEAD,
    AgentCall,
    AgentDeps,
    LeadPlan,
    copy_designs,
    get_agent,
    invoke_agent,
    run_review_agent,
)
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

    plan = await _lead_plan(ctx, deps, mode=mode, changes=changes, flow_hint=flow)
    scenarios = plan.scenarios or ([flow] if flow else [])
    review_agents = summary.agents  # Code reviewer / Design reviewer; functionality runs below

    lines = [plan.summary.strip()] if plan.summary.strip() else []
    if scenarios:
        lines.append(f"Test case scenarios ({len(scenarios)}):")
        lines += [f"  {i}. {_first_line(s)}" for i, s in enumerate(scenarios, 1)]
    if review_agents:
        lines.append("Also reviewing: " + ", ".join(review_agents))
    ctx.record.plan_summary = "\n".join(lines)
    ctx.save()

    # Functionality is always checked first: the scenarios are planned before anything runs,
    # and every one of them is tested before the (slower, less important) code/design review.
    if scenarios:
        ctx.event(f"{len(scenarios)} test case scenario(s) planned", source=QA_LEAD)
        for i, scenario in enumerate(scenarios, 1):
            ctx.event(
                f"Testing scenario {i}/{len(scenarios)}: {_first_line(scenario)}",
                source=FUNCTIONALITY_TESTER,
            )
            await run_review_agent(
                ctx,
                deps,
                AgentCall(
                    agent=get_agent(s, FUNCTIONALITY_TESTER),
                    task=f"Test case scenario {i} of {len(scenarios)}:\n{scenario}",
                    mode=mode,
                    # Distinct evidence folder per scenario: without it, scenario 2's
                    # screenshots and recorder log would overwrite scenario 1's.
                    work_dir_name=f"{FUNCTIONALITY_TESTER}-{i}",
                ),
            )
    elif flow:
        ctx.event("Functionality tester skipped: the QA Lead gave no plan", level="warn")

    for name in review_agents:
        if name == CODE_REVIEWER:
            focus = f"\nFocus on: {plan.code_review_focus}" if plan.code_review_focus else ""
            await run_review_agent(
                ctx,
                deps,
                AgentCall(
                    agent=get_agent(s, name),
                    task="Review this change against the repo's guidelines and skills." + focus,
                    mode=mode,
                    context=changes,
                ),
            )
        elif name == DESIGN_REVIEWER:
            await _design_reviews(ctx, deps, mode, plan.design_routes, changes)
        elif name == API_CHECKER:
            await run_review_agent(
                ctx,
                deps,
                AgentCall(
                    agent=get_agent(s, name),
                    task="Compare the frontend's API calls with the backend's routes for this "
                    "change.",
                    mode=mode,
                    context=changes,
                ),
            )


def _first_line(text: str) -> str:
    for line in text.strip().splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return "(empty)"


async def _lead_plan(
    ctx: RunContext, deps: AgentDeps, *, mode: RunMode, changes: list[str], flow_hint: str | None
) -> LeadPlan:
    if changes:
        ask = (
            "Plan the checks for this change: list the routes whose UI changed (for the Design "
            "reviewer) and suggest what the Code reviewer should focus on. Then write 1-4 "
            "concrete test case scenarios for the Functionality tester: the normal path first, "
            "then the important edge cases the change implies. Each scenario is a short numbered "
            "plain-English flow ending with an Expected: line."
        )
    else:
        ask = (
            "There is no local code diff to check — only a flow the developer wants tested in "
            "the running app. Turn it into 1-4 concrete test case scenarios for the "
            "Functionality tester: the normal path first, then the important edge cases it "
            "implies. Each scenario is a short numbered plain-English flow ending with an "
            "Expected: line. Leave design_routes empty and don't suggest a code review focus."
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


async def _design_reviews(
    ctx: RunContext, deps: AgentDeps, mode: RunMode, routes: list[str], changes: list[str]
) -> None:
    s = deps.settings
    clean = [r for r in dict.fromkeys(routes) if r.startswith("/")][:MAX_DESIGN_ROUTES]
    if not clean:
        ctx.event("Design reviewer skipped: the QA Lead found no changed route", level="warn")
        return
    for route in clean:
        designs = copy_designs(s, route, ctx.dir)
        if not designs and not s.figma_mcp_url:
            ctx.event(
                f"Design reviewer skipped {route}: no design PNG in {s.designs_dir}", level="warn"
            )
            continue
        await run_review_agent(ctx, deps, design_call(deps, route, mode, designs, changes))


def design_call(
    deps: AgentDeps,
    route: str,
    mode: RunMode,
    designs: dict[str, Path],
    changes: list[str] | None = None,
) -> AgentCall:
    url = f"{deps.settings.app_url.rstrip('/')}{route}"
    design_lines = [f"- Design ({v}): {p}" for v, p in designs.items()] or [
        "- No PNG for this route: use the Figma MCP server to get the design frame."
    ]
    return AgentCall(
        agent=get_agent(deps.settings, DESIGN_REVIEWER),
        task=f"Compare {url} with its design at desktop (1440x900) and mobile (390x844) size.",
        mode=mode,
        route=route,
        designs=designs,
        context=["", "## Designs", *design_lines, *(changes or [])],
    )


async def run_single_agent(
    ctx: RunContext, deps: AgentDeps, *, agent: str, task: str, route: str | None, mode: RunMode
) -> None:
    """Run one agent on demand (e.g. Design reviewer on /pricing)."""
    s = deps.settings
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
    elif agent in (CODE_REVIEWER, API_CHECKER):
        repo = s.app_repo_path
        if repo is None or not await git.is_repo(repo):
            raise PreconditionError("APP_REPO_PATH must point at the app's git repository")
        since = await git.merge_base(repo, s.diff_base) or "HEAD"
        diff_path = ctx.dir / "diff.patch"
        await asyncio.to_thread(diff_path.write_text, await git.diff(repo, since))
        ctx.add_artifact("Diff", diff_path, "code")
        call = AgentCall(
            agent=get_agent(s, agent),
            task=task,
            mode=mode,
            context=["", "## Change under review", f"- Diff against {s.diff_base}: {diff_path}"],
        )
    elif agent in (QA_LEAD, "test-writer"):
        raise PreconditionError(f"{agent} runs from Check my change / Save as test, not on its own")
    else:
        call = AgentCall(agent=get_agent(s, agent), task=task, mode=mode, route=route)
    await run_review_agent(ctx, deps, call)
