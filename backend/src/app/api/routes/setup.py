import asyncio

from fastapi import APIRouter

from app.api.deps import ClaudeDep, ProbeDep, QaConfigDep, SettingsDep
from app.schemas.setup import AgentInfo, QaConfigSummary, SetupCheck
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


@router.get("/qa-config", response_model=QaConfigSummary)
async def qa_config(settings: SettingsDep, qa: QaConfigDep) -> QaConfigSummary:
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
    )
