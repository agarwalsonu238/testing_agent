from typing import Annotated

from fastapi import APIRouter, Path, Query, status
from fastapi.responses import FileResponse

from app.api.deps import DepsDep, ManagerDep
from app.schemas.runs import (
    AgentRunRequest,
    ApproveRequest,
    CheckChangeRequest,
    Finding,
    FindingDecision,
    QuickScanRequest,
    RunDetail,
    RunEventsResponse,
    RunSummary,
    SaveTestRequest,
)
from app.services import run_jobs
from app.services.reports import to_detail, to_summary
from app.services.run_store import RUN_ID_PATTERN

router = APIRouter(prefix="/runs", tags=["runs"])

RunId = Annotated[str, Path(pattern=RUN_ID_PATTERN.pattern)]
FindingId = Annotated[str, Path(pattern=r"^f\d{1,5}$")]


@router.post("/quick-scan", response_model=RunDetail, status_code=status.HTTP_202_ACCEPTED)
async def start_quick_scan(body: QuickScanRequest, manager: ManagerDep, deps: DepsDep) -> RunDetail:
    return to_detail(await run_jobs.start_quick_scan(manager, deps, body.mode, body))


@router.post("/check-change", response_model=RunDetail, status_code=status.HTTP_202_ACCEPTED)
async def start_check_change(
    body: CheckChangeRequest, manager: ManagerDep, deps: DepsDep
) -> RunDetail:
    return to_detail(await run_jobs.start_check_change(manager, deps, body))


@router.post("/agent", response_model=RunDetail, status_code=status.HTTP_202_ACCEPTED)
async def start_agent_run(body: AgentRunRequest, manager: ManagerDep, deps: DepsDep) -> RunDetail:
    return to_detail(await run_jobs.start_agent_run(manager, deps, body))


@router.get("", response_model=list[RunSummary])
async def list_runs(manager: ManagerDep) -> list[RunSummary]:
    return [to_summary(r) for r in await manager.all_runs()]


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: RunId, manager: ManagerDep) -> RunDetail:
    return to_detail(await manager.get(run_id))


@router.get("/{run_id}/events", response_model=RunEventsResponse)
async def get_run_events(
    run_id: RunId, manager: ManagerDep, after: Annotated[int, Query(ge=0)] = 0
) -> RunEventsResponse:
    events = await manager.events(run_id, after)
    record = await manager.get(run_id)
    return RunEventsResponse(events=events, done=record.status == "finished")


@router.get("/{run_id}/files/{path:path}", response_class=FileResponse)
async def get_run_file(run_id: RunId, path: str, manager: ManagerDep) -> FileResponse:
    return FileResponse(await manager.file(run_id, path))


@router.post("/{run_id}/cancel", response_model=RunDetail)
async def cancel_run(run_id: RunId, manager: ManagerDep) -> RunDetail:
    await manager.cancel(run_id)
    return to_detail(await manager.get(run_id))


@router.post("/{run_id}/approve", response_model=RunDetail)
async def approve_run(run_id: RunId, body: ApproveRequest, manager: ManagerDep) -> RunDetail:
    """Let a run that is waiting on the developer carry on with the reviewed test cases."""
    await manager.approve(run_id, body.skip)
    return to_detail(await manager.get(run_id))


@router.post("/{run_id}/save-test", response_model=RunDetail, status_code=status.HTTP_202_ACCEPTED)
async def save_test(
    run_id: RunId, body: SaveTestRequest, manager: ManagerDep, deps: DepsDep
) -> RunDetail:
    return to_detail(await run_jobs.start_save_test(manager, deps, run_id, body))


@router.post("/{run_id}/findings/{finding_id}/decision", response_model=Finding)
async def decide_finding(
    run_id: RunId, finding_id: FindingId, body: FindingDecision, manager: ManagerDep
) -> Finding:
    reason = body.reason.strip() if body.reason else None
    return await manager.decide(run_id, finding_id, body.decision == "accept", reason)
