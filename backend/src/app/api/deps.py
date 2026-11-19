from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.integrations.claude_code import ClaudeCode
from app.integrations.http_probe import HttpProbe
from app.schemas.qa_config import QaConfig
from app.services.agents import AgentDeps
from app.services.qa_config import load_qa_config
from app.services.run_manager import RunManager

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_run_manager(request: Request) -> RunManager:
    manager: RunManager = request.app.state.run_manager
    return manager


def get_probe(request: Request) -> HttpProbe:
    probe: HttpProbe = request.app.state.probe
    return probe


def get_claude(settings: SettingsDep) -> ClaudeCode:
    return ClaudeCode(settings)


def get_qa_config(settings: SettingsDep) -> QaConfig:
    return load_qa_config(settings)


def get_agent_deps(
    settings: SettingsDep,
    qa: Annotated[QaConfig, Depends(get_qa_config)],
    claude: Annotated[ClaudeCode, Depends(get_claude)],
    probe: Annotated[HttpProbe, Depends(get_probe)],
) -> AgentDeps:
    return AgentDeps(settings=settings, qa=qa, claude=claude, probe=probe)


ManagerDep = Annotated[RunManager, Depends(get_run_manager)]
DepsDep = Annotated[AgentDeps, Depends(get_agent_deps)]
ClaudeDep = Annotated[ClaudeCode, Depends(get_claude)]
ProbeDep = Annotated[HttpProbe, Depends(get_probe)]
QaConfigDep = Annotated[QaConfig, Depends(get_qa_config)]
