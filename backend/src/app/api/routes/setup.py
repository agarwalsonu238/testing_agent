import asyncio

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ClaudeDep, FolderPickerDep, ProbeDep, QaConfigDep, SettingsDep
from app.core.config import Settings
from app.integrations.folder_picker import FolderPicker, FolderPickerError
from app.schemas.setup import AgentInfo, PickedFolder, QaConfigSummary, SetupCheck
from app.services.agents import PIPELINE_ONLY, load_agents
from app.services.qa_config import list_designs
from app.services.setup_check import run_setup_check

router = APIRouter(tags=["setup"])


@router.get("/setup-check", response_model=SetupCheck)
async def setup_check(
    settings: SettingsDep, claude: ClaudeDep, probe: ProbeDep, live: bool = False
) -> SetupCheck:
    """`live=true` also makes a one-line Claude Code run on the developer's login."""
    return await run_setup_check(settings, claude, probe, live)


def _can_pick(settings: Settings, picker: FolderPicker) -> bool:
    # A backend with an API token is deployed somewhere else: a window there would help nobody.
    token = settings.api_auth_token
    return picker.available() and (token is None or not token.get_secret_value())


@router.get("/qa-config", response_model=QaConfigSummary)
async def qa_config(
    settings: SettingsDep, qa: QaConfigDep, picker: FolderPickerDep
) -> QaConfigSummary:
    agents = load_agents(settings.agents_dir)
    # Only offer the default folder when it exists, so the form never shows an unusable path
    # (like .env.example's placeholder) as if it were the default.
    repo = settings.app_repo_path
    repo_ok = repo is not None and await asyncio.to_thread(repo.is_dir)
    return QaConfigSummary(
        app_url=settings.app_url,
        app_repo_path=str(repo) if repo_ok else None,
        pages=[p.path for p in qa.pages],
        viewports=list(qa.viewports),
        agents=[
            AgentInfo(
                name=a.name, description=a.description, standalone=a.name not in PIPELINE_ONLY
            )
            for a in agents.values()
        ],
        designs=list_designs(settings),
        can_pick_folder=_can_pick(settings, picker),
    )


@router.post("/pick-folder", response_model=PickedFolder)
async def pick_folder(settings: SettingsDep, picker: FolderPickerDep) -> PickedFolder:
    """Open the Mac's folder picker on this machine and return the chosen path."""
    if not _can_pick(settings, picker):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The folder picker only works on a local Mac backend"
        )
    repo = settings.app_repo_path
    start = repo if repo is not None and await asyncio.to_thread(repo.is_dir) else None
    try:
        chosen = await picker.pick(start)
    except FolderPickerError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Couldn't open the folder picker: {exc}"
        ) from exc
    return PickedFolder(path=str(chosen) if chosen else None)
