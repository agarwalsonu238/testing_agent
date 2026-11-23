from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import SecretStr

from app.api.deps import get_claude
from app.core.config import Settings
from app.integrations.claude_code import ClaudeCode


class FakeClaude(ClaudeCode):
    """Stands in for the `claude` CLI at the integration boundary."""

    def __init__(self, settings: Settings, method: str = "claude.ai") -> None:
        super().__init__(settings)
        self.method = method
        self.smoke_calls = 0

    async def version(self) -> str | None:
        return "2.1.328"

    async def auth_status(self) -> dict[str, Any] | None:
        return {"loggedIn": True, "authMethod": self.method, "subscriptionType": "pro"}

    async def smoke_test(self) -> tuple[bool, str]:
        self.smoke_calls += 1
        return True, "Reply: OK"


def _items(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["key"]: item for item in body["items"]}


async def test_setup_check_reports_each_item(
    client: AsyncClient, app: FastAPI, settings: Settings
) -> None:
    fake = FakeClaude(settings)
    app.dependency_overrides[get_claude] = lambda: fake

    body = (await client.get("/api/v1/setup-check")).json()
    items = _items(body)

    assert items["claude"]["status"] == "pass"
    assert items["login"]["detail"] == "Claude Pro plan (claude.ai)"
    assert items["api_key"]["status"] == "pass"
    assert items["smoke"]["status"] == "skip" and fake.smoke_calls == 0
    assert items["app"]["status"] == "fail"  # FakeProbe: app not running
    assert items["app_repo"]["status"] == "warn"
    assert items["agents"]["status"] == "pass"
    assert items["reviewer"]["status"] == "pass" and "Claude" in items["reviewer"]["detail"]
    assert body["ready"] is False


async def test_live_setup_check_runs_the_login_test(
    client: AsyncClient, app: FastAPI, settings: Settings
) -> None:
    fake = FakeClaude(settings)
    app.dependency_overrides[get_claude] = lambda: fake
    items = _items((await client.get("/api/v1/setup-check?live=true")).json())
    assert items["smoke"]["status"] == "pass" and fake.smoke_calls == 1


async def test_api_key_login_fails_the_setup_check(
    client: AsyncClient, app: FastAPI, settings: Settings
) -> None:
    settings.anthropic_api_key = SecretStr("sk-ant-x")
    fake = FakeClaude(settings, method="api_key")
    app.dependency_overrides[get_claude] = lambda: fake
    body = (await client.get("/api/v1/setup-check?live=true")).json()
    items = _items(body)
    assert items["login"]["status"] == "fail"
    assert items["api_key"]["status"] == "fail"
    assert items["smoke"]["status"] == "skip" and fake.smoke_calls == 0
    assert "sk-ant-x" not in str(body)
