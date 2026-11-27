import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.integrations.claude_code import ClaudeCode
from app.integrations.external_reviewer import ExternalReviewer
from app.integrations.folder_picker import FolderPicker
from app.integrations.http_probe import HttpProbe
from app.schemas.qa_config import QaConfig
from app.services.agents import AgentDeps
from app.services.qa_config import load_qa_config
from app.services.run_manager import RunManager

SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_api_key(request: Request, settings: SettingsDep) -> None:
    """Gate every /api/v1 request once API_AUTH_TOKEN is set (a deployed backend).

    Accepts the key as the `X-API-Key` header (normal requests) or a `key` query parameter
    (for <img>/<a> tags, which can't set custom headers — e.g. screenshot evidence). A no-op
    when unset, matching the local-only default (127.0.0.1 binding is the boundary then).
    """
    token = settings.api_auth_token
    if token is None or not token.get_secret_value():
        return
    supplied = request.headers.get("x-api-key") or request.query_params.get("key") or ""
    if not hmac.compare_digest(supplied, token.get_secret_value()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid X-API-Key")


def get_run_manager(request: Request) -> RunManager:
    manager: RunManager = request.app.state.run_manager
    return manager


def get_probe(request: Request) -> HttpProbe:
    probe: HttpProbe = request.app.state.probe
    return probe


def get_claude(settings: SettingsDep) -> ClaudeCode:
    return ClaudeCode(settings)


def get_folder_picker() -> FolderPicker:
    return FolderPicker()


def get_qa_config(settings: SettingsDep) -> QaConfig:
    return load_qa_config(settings)


def get_agent_deps(
    settings: SettingsDep,
    qa: Annotated[QaConfig, Depends(get_qa_config)],
    claude: Annotated[ClaudeCode, Depends(get_claude)],
    probe: Annotated[HttpProbe, Depends(get_probe)],
) -> AgentDeps:
    return AgentDeps(
        settings=settings,
        qa=qa,
        claude=claude,
        probe=probe,
        reviewer=ExternalReviewer.from_settings(settings),
    )


ManagerDep = Annotated[RunManager, Depends(get_run_manager)]
DepsDep = Annotated[AgentDeps, Depends(get_agent_deps)]
ClaudeDep = Annotated[ClaudeCode, Depends(get_claude)]
ProbeDep = Annotated[HttpProbe, Depends(get_probe)]
QaConfigDep = Annotated[QaConfig, Depends(get_qa_config)]
FolderPickerDep = Annotated[FolderPicker, Depends(get_folder_picker)]
