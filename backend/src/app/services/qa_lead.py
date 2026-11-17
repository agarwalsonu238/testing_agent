"""Check my change: the QA Lead reads the diff and runs the right agents.

Which agents run is a fixed rule (plan section 2): UI files → Design reviewer, logic or API →
Functionality tester, every change → Code reviewer. The QA Lead agent adds the details the rule
can't: which routes changed, a flow to test, and what the code review should focus on.
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
        """Agents the fixed rule requires, in run order."""
        if not self.files:
            return []
        needed = [CODE_REVIEWER]
        if self.ui:
            needed.append(DESIGN_REVIEWER)
        if self.logic:
            needed.append(FUNCTIONALITY_TESTER)
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
    if not summary.files:
        ctx.record.plan_summary = f"No changes since {base}; nothing to check."
        ctx.save()
        return

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
        f"{len(summary.files)} changed file(s): {len(summary.ui)} UI, {len(summary.logic)} logic",
    )

    plan = await _lead_plan(ctx, deps, mode=mode, changes=changes, wants_flow=flow is None)
    flow_text = flow or plan.flow
    lines = [plan.summary.strip()] if plan.summary.strip() else []
    lines.append("Agents: " + ", ".join(summary.agents))
    ctx.record.plan_summary = "\n".join(lines)
    ctx.save()

    for name in summary.agents:
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
        elif name == FUNCTIONALITY_TESTER:
            if not flow_text:
                ctx.event("Functionality tester skipped: describe a flow to test it", level="warn")
                continue
            await run_review_agent(
                ctx,
                deps,
                AgentCall(
                    agent=get_agent(s, name), task=f"Test this flow:\n{flow_text}", mode=mode
                ),
            )


async def _lead_plan(
    ctx: RunContext, deps: AgentDeps, *, mode: RunMode, changes: list[str], wants_flow: bool
) -> LeadPlan:
    ask = (
        "Plan the checks for this change: list the routes whose UI changed (for the Design "
        "reviewer), suggest what the Code reviewer should focus on"
    )
    ask += ", and write a short numbered flow for the Functionality tester." if wants_flow else "."
    try:
        run = await invoke_agent(
            ctx,
            deps,
            AgentCall(
                agent=get_agent(deps.settings, QA_LEAD),
                task=ask,
                mode=mode,
                context=changes,
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
    elif agent == CODE_REVIEWER:
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
