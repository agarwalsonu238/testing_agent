"""Start each kind of run: check preconditions up front (so the request fails fast), then hand
the job to the RunManager."""

from datetime import datetime

from app.core.errors import PreconditionError
from app.integrations.claude_code import ClaudeCodeError
from app.schemas.runs import (
    AgentRunRequest,
    CheckChangeRequest,
    FindingItem,
    FindingStatus,
    RunParams,
    RunRecord,
    SaveTestRequest,
)
from app.services.agents import AgentDeps, get_agent
from app.services.qa_lead import run_check_change, run_single_agent
from app.services.quick_scan import run_quick_scan
from app.services.run_manager import RunContext, RunManager
from app.services.saved_tests import find_saved_test, run_saved_test
from app.services.test_writer import ensure_can_save, save_as_test

_SEVERITY_ORDER = {"High": 0, "Medium": 1, "Warning": 2}


def _ensure_subscription(deps: AgentDeps) -> None:
    try:
        deps.claude.ensure_no_billed_credentials()
    except ClaudeCodeError as exc:
        raise PreconditionError(str(exc)) from exc


async def start_quick_scan(manager: RunManager, deps: AgentDeps, mode: str) -> RunRecord:
    """Start Quick Scan (no AI). Raises ConflictError when a run is active."""
    params = RunParams(mode="real" if mode == "real" else "mocked")

    async def job(ctx: RunContext) -> None:
        await run_quick_scan(
            ctx, settings=deps.settings, qa=deps.qa, mode=params.mode, probe=deps.probe
        )

    return await manager.start("quick-scan", f"Quick Scan · {params.mode}", params, job)


async def start_check_change(
    manager: RunManager, deps: AgentDeps, req: CheckChangeRequest
) -> RunRecord:
    """Start Check my change. Raises PreconditionError (API key set) or ConflictError."""
    _ensure_subscription(deps)
    params = RunParams(mode=req.mode, base_ref=req.base_ref, flow=req.flow)

    async def job(ctx: RunContext) -> None:
        await run_check_change(ctx, deps, mode=req.mode, base_ref=req.base_ref, flow=req.flow)

    return await manager.start("check-change", "Check my change", params, job)


async def start_agent_run(manager: RunManager, deps: AgentDeps, req: AgentRunRequest) -> RunRecord:
    """Run one agent. Raises NotFoundError (unknown agent), PreconditionError or ConflictError."""
    _ensure_subscription(deps)
    get_agent(deps.settings, req.agent)
    params = RunParams(mode=req.mode, agent=req.agent, task=req.task, route=req.route)
    title = f"{req.agent}" + (f" · {req.route}" if req.route else "")

    async def job(ctx: RunContext) -> None:
        await run_single_agent(
            ctx, deps, agent=req.agent, task=req.task, route=req.route, mode=req.mode
        )

    return await manager.start("agent", title, params, job)


async def start_save_test(
    manager: RunManager, deps: AgentDeps, source_id: str, req: SaveTestRequest
) -> RunRecord:
    """Save a passing flow as a test. Raises ConflictError when the source isn't a passing flow."""
    _ensure_subscription(deps)
    source = await manager.get(source_id)
    ensure_can_save(source)
    params = RunParams(mode=source.params.mode, source_run_id=source.id)

    async def job(ctx: RunContext) -> None:
        await save_as_test(ctx, deps, source, req)

    return await manager.start("save-test", "Save as test", params, job)


async def start_saved_test(manager: RunManager, deps: AgentDeps, test_id: str) -> RunRecord:
    """Re-run a saved test with plain Playwright. Raises NotFoundError for unknown IDs."""
    test = find_saved_test(deps.settings, deps.qa, test_id)
    params = RunParams(test_id=test.id)

    async def job(ctx: RunContext) -> None:
        await run_saved_test(ctx, deps, test)

    return await manager.start("saved-test", f"Saved test {test.id}", params, job)


def collect_findings(
    records: list[RunRecord], status: FindingStatus | None, agent: str | None
) -> list[FindingItem]:
    """Findings across the kept runs, newest run first, then by severity."""
    items: list[tuple[datetime, int, FindingItem]] = []
    for record in records:
        for finding in record.findings:
            if (status and finding.status != status) or (agent and finding.agent != agent):
                continue
            item = FindingItem(
                **finding.model_dump(),
                run_id=record.id,
                run_title=record.title,
                run_started_at=record.started_at,
            )
            items.append((record.started_at, _SEVERITY_ORDER[finding.severity], item))
    items.sort(key=lambda t: (-t[0].timestamp(), t[1]))
    return [item for _, _, item in items]
