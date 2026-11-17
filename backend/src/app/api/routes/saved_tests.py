from typing import Annotated

from fastapi import APIRouter, Path, status

from app.api.deps import DepsDep, ManagerDep, QaConfigDep, SettingsDep
from app.schemas.runs import RunDetail
from app.schemas.setup import SavedTest
from app.services import run_jobs
from app.services.reports import to_detail
from app.services.saved_tests import list_saved_tests

router = APIRouter(prefix="/saved-tests", tags=["saved-tests"])

TestId = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,40}$")]


@router.get("", response_model=list[SavedTest])
async def get_saved_tests(settings: SettingsDep, qa: QaConfigDep) -> list[SavedTest]:
    return list_saved_tests(settings, qa)


@router.post("/{test_id}/run", response_model=RunDetail, status_code=status.HTTP_202_ACCEPTED)
async def run_saved_test(test_id: TestId, manager: ManagerDep, deps: DepsDep) -> RunDetail:
    return to_detail(await run_jobs.start_saved_test(manager, deps, test_id))
