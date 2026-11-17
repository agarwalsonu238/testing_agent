from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ManagerDep
from app.schemas.runs import AGENT_NAME_PATTERN, FindingItem, FindingStatus
from app.services.run_jobs import collect_findings

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("", response_model=list[FindingItem])
async def list_findings(
    manager: ManagerDep,
    status: FindingStatus | None = None,
    agent: Annotated[str | None, Query(pattern=AGENT_NAME_PATTERN)] = None,
) -> list[FindingItem]:
    """To review: findings from the kept runs (filter `status=open` for the review list)."""
    return collect_findings(await manager.all_runs(), status, agent)
