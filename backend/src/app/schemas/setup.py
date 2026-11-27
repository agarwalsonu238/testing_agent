from typing import Literal

from pydantic import BaseModel

CheckStatus = Literal["pass", "warn", "fail", "skip"]


class SetupItem(BaseModel):
    key: str
    label: str
    status: CheckStatus
    detail: str
    fix: str | None = None


class SetupCheck(BaseModel):
    ready: bool  # True when nothing is "fail"
    items: list[SetupItem]


class AgentInfo(BaseModel):
    name: str
    description: str
    # False for roles that only run inside another flow (QA Lead, reviewer, reporter, Test writer).
    standalone: bool = True


class QaConfigSummary(BaseModel):
    app_url: str
    app_repo_path: str | None
    pages: list[str]
    viewports: list[str]
    agents: list[AgentInfo]
    designs: list[str]  # design file names found in DESIGNS_DIR
    # True when the backend can open the Mac's folder picker (local Mac, no API token).
    can_pick_folder: bool = False


class PickedFolder(BaseModel):
    path: str | None  # None when the developer cancelled


class SavedTest(BaseModel):
    id: str
    title: str
    file: str
    folder: str | None = None
    created_at: str | None = None
    source_run_id: str | None = None
