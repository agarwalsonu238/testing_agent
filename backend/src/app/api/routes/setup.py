from fastapi import APIRouter

from app.api.deps import ClaudeDep, ProbeDep, QaConfigDep, SettingsDep
from app.schemas.setup import AgentInfo, QaConfigSummary, SetupCheck
from app.services.agents import load_agents
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
    return QaConfigSummary(
        app_url=settings.app_url,
        app_repo_path=str(settings.app_repo_path) if settings.app_repo_path else None,
        pages=[p.path for p in qa.pages],
        viewports=list(qa.viewports),
        agents=[AgentInfo(name=a.name, description=a.description) for a in agents.values()],
        designs=list_designs(settings),
    )
