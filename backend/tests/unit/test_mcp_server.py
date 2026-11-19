"""The MCP server is a thin client over the backend's own HTTP API, so these tests fake that
API with an httpx.MockTransport rather than running a real backend."""

from collections.abc import Callable

import httpx
import pytest

from app import mcp_server
from app.core.config import Settings


def _patch_client(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    class _Client(httpx.AsyncClient):
        def __init__(self, *args: object, **kwargs: object) -> None:
            kwargs.pop("transport", None)
            super().__init__(*args, transport=httpx.MockTransport(handler), **kwargs)  # type: ignore[arg-type]

    # `mcp_server` imported the same `httpx` module object, so patching it here reaches there too.
    monkeypatch.setattr(httpx, "AsyncClient", _Client)


def _patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(mcp_backend_url="http://test/api/v1", mcp_dashboard_url="http://dash")
    monkeypatch.setattr(mcp_server, "get_settings", lambda: settings)


async def test_quick_scan_polls_until_finished_and_drops_non_open_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_settings(monkeypatch)
    monkeypatch.setattr(mcp_server, "POLL_S", 0.01)
    gets = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert request.url.path == "/api/v1/runs/quick-scan"
            return httpx.Response(202, json={"id": "run-1"})
        gets["n"] += 1
        status = "finished" if gets["n"] >= 2 else "running"
        return httpx.Response(
            200,
            json={
                "id": "run-1",
                "status": status,
                "verdict": "FAILING" if status == "finished" else None,
                "blocked_reason": None,
                "plan_summary": "1 page scanned",
                "findings": [
                    {
                        "severity": "High",
                        "title": "Broke",
                        "location": "/ · desktop",
                        "expected": "ok",
                        "actual": "boom",
                        "status": "open",
                    },
                    {
                        "severity": "Medium",
                        "title": "Already ignored",
                        "location": "/ · desktop",
                        "expected": "ok",
                        "actual": "meh",
                        "status": "ignored",
                    },
                ],
            },
        )

    _patch_client(monkeypatch, handler)
    result = await mcp_server.quick_scan(mode="mocked")

    assert gets["n"] == 2  # polled once while running, once more when finished
    assert result["run_id"] == "run-1"
    assert result["status"] == "finished"
    assert result["verdict"] == "FAILING"
    assert result["dashboard_url"] == "http://dash/runs/run-1"
    assert result["open_findings"] == [
        {
            "severity": "High",
            "title": "Broke",
            "location": "/ · desktop",
            "expected": "ok",
            "actual": "boom",
        }
    ]


async def test_check_change_surfaces_a_refusal_as_an_error_not_an_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(412, json={"detail": "ANTHROPIC_API_KEY is set"})

    _patch_client(monkeypatch, handler)
    result = await mcp_server.check_change(flow="test the thing")
    assert "ANTHROPIC_API_KEY" in result["error"]


async def test_get_run_reports_an_unknown_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)
    _patch_client(monkeypatch, lambda request: httpx.Response(404))

    assert await mcp_server.get_run("nope") == {"error": "No run nope"}


async def test_list_open_findings_only_asks_for_open(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["status"] == "open"
        return httpx.Response(
            200,
            json=[
                {
                    "run_id": "r1",
                    "severity": "High",
                    "title": "x",
                    "location": "/",
                    "expected": "a",
                    "actual": "b",
                }
            ],
        )

    _patch_client(monkeypatch, handler)
    result = await mcp_server.list_open_findings()
    assert result == [
        {
            "run_id": "r1",
            "severity": "High",
            "title": "x",
            "location": "/",
            "expected": "a",
            "actual": "b",
        }
    ]


async def test_unreachable_backend_is_a_tool_error_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    _patch_client(monkeypatch, handler)
    result = await mcp_server.quick_scan()
    assert "Can't reach the QA backend" in result["error"]
    assert "run-local-dev.sh" in result["error"]


async def test_another_active_run_is_reported_not_queued(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)
    _patch_client(
        monkeypatch,
        lambda request: httpx.Response(409, json={"detail": "Another run is in progress"}),
    )

    result = await mcp_server.quick_scan()
    assert "Another run is in progress" in result["error"]
