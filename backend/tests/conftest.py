from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_claude, get_probe
from app.core.config import Settings, get_settings
from app.main import create_app

QA_DIR = Path(__file__).resolve().parents[1] / "qa"


class FakeProbe:
    def __init__(self, reachable: bool = False) -> None:
        self.ok = reachable

    async def reachable(self, url: str) -> tuple[bool, str]:
        return self.ok, f"{'HTTP 200' if self.ok else 'ConnectError: no answer'} from {url}"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        runs_dir=tmp_path / "runs",
        qa_dir=QA_DIR,
        designs_dir=tmp_path / "designs",
        app_url="http://127.0.0.1:9",
        app_repo_path=None,
        anthropic_api_key=None,
        anthropic_auth_token=None,
        claude_code_oauth_token=None,
        test_account_email=None,
        test_account_password=None,
        figma_mcp_url=None,
    )


@pytest.fixture
def probe() -> FakeProbe:
    return FakeProbe(reachable=False)


@pytest.fixture
def app(settings: Settings, probe: FakeProbe) -> FastAPI:
    application = create_app(settings)
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_probe] = lambda: probe
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await app.state.run_manager.shutdown()


__all__ = ["FakeProbe", "get_claude"]
