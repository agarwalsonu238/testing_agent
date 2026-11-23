"""The staged pipeline: plan → review → (approve) → run every executor → report every one."""

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_claude
from app.core.config import Settings
from app.services.run_manager import RunManager
from tests.api.test_runs_api import _FakeClaudeCode, _init_repo_with_no_pending_changes


def _cases(*titles: str) -> list[dict[str, Any]]:
    return [
        {
            "title": t,
            "agent": "functionality-tester",
            "steps": [f"1. Do {t}."],
            "expected": f"{t} works",
        }
        for t in titles
    ]


def _replies(titles: list[str], case_results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        "qa-lead": {"summary": "Plan.", "design_routes": [], "test_cases": _cases(*titles)},
        "test-case-reviewer": {
            "cases": [{**c, "review_status": "approved"} for c in _cases(*titles)]
        },
        "functionality-tester": {"case_observations": [], "steps": []},
        "qa-reporter": {
            "summary": "Checked.",
            "findings": [],
            "steps": [],
            "case_results": case_results,
        },
    }


async def _setup_repo(settings: Settings, tmp_path: Path) -> None:
    settings.app_repo_path = tmp_path / "app-repo"
    await _init_repo_with_no_pending_changes(settings.app_repo_path)


async def _until(client: AsyncClient, run_id: str, predicate: Any) -> dict[str, Any]:
    for _ in range(200):
        detail = (await client.get(f"/api/v1/runs/{run_id}")).json()
        if predicate(detail):
            return detail  # type: ignore[no-any-return]
        await asyncio.sleep(0.05)
    raise AssertionError("the run never reached the expected state")


async def test_each_case_result_is_written_to_its_own_case_only(
    client: AsyncClient, app: FastAPI, settings: Settings, tmp_path: Path
) -> None:
    """Regression: the first call's reporter used to mark every other functionality case
    'skipped — did not report', because it updated all of the agent's planned cases."""
    await _setup_repo(settings, tmp_path)
    fake = _FakeClaudeCode(
        _replies(
            ["Book", "Cancel"],
            [{"id": "TC-1", "status": "pass"}, {"id": "TC-2", "status": "fail", "note": "boom"}],
        )
    )
    app.dependency_overrides[get_claude] = lambda: fake
    try:
        response = await client.post(
            "/api/v1/runs/check-change", json={"mode": "mocked", "flow": "Book then cancel"}
        )
        run_id = response.json()["id"]
        await app.state.run_manager.wait()
    finally:
        del app.dependency_overrides[get_claude]

    detail = (await client.get(f"/api/v1/runs/{run_id}")).json()
    by_id = {c["id"]: c for c in detail["test_cases"]}
    assert by_id["TC-1"]["status"] == "pass"
    assert by_id["TC-2"]["status"] == "fail" and by_id["TC-2"]["note"] == "boom"
    # Both executors ran before either reporter wrote anything.
    assert fake.agents_called == [
        "qa-lead",
        "test-case-reviewer",
        "functionality-tester",
        "functionality-tester",
        "qa-reporter",
        "qa-reporter",
    ]
    assert detail["stage"] == "done" and detail["awaiting_approval"] is False


async def test_run_pauses_for_approval_and_skips_what_the_developer_skips(
    client: AsyncClient, app: FastAPI, settings: Settings, tmp_path: Path
) -> None:
    await _setup_repo(settings, tmp_path)
    fake = _FakeClaudeCode(_replies(["Book", "Cancel"], [{"id": "TC-2", "status": "pass"}]))
    app.dependency_overrides[get_claude] = lambda: fake
    try:
        response = await client.post(
            "/api/v1/runs/check-change",
            json={"mode": "mocked", "flow": "Book then cancel", "approve_plan": True},
        )
        run_id = response.json()["id"]
        paused = await _until(client, run_id, lambda d: d["awaiting_approval"])
        assert paused["stage"] == "awaiting_approval" and paused["status"] == "running"
        assert "functionality-tester" not in fake.agents_called  # nothing ran yet
        assert [c["review_status"] for c in paused["test_cases"]] == ["approved", "approved"]

        approved = await client.post(f"/api/v1/runs/{run_id}/approve", json={"skip": ["TC-1"]})
        assert approved.status_code == 200
        await app.state.run_manager.wait()
    finally:
        del app.dependency_overrides[get_claude]

    detail = (await client.get(f"/api/v1/runs/{run_id}")).json()
    by_id = {c["id"]: c for c in detail["test_cases"]}
    assert by_id["TC-1"]["status"] == "skipped"
    assert by_id["TC-1"]["note"] == "You chose not to run this case"
    assert by_id["TC-2"]["status"] == "pass"
    assert fake.agents_called.count("functionality-tester") == 1


async def test_approving_a_run_that_is_not_waiting_is_409_and_unknown_is_404(
    client: AsyncClient, app: FastAPI
) -> None:
    manager: RunManager = app.state.run_manager
    from app.schemas.runs import RunParams

    record = manager.store.create("agent", "x", RunParams())
    ok = await client.post(f"/api/v1/runs/{record.id}/approve", json={"skip": []})
    assert ok.status_code == 409
    missing = await client.post("/api/v1/runs/20200101-000000-agent-abcdef/approve", json={})
    assert missing.status_code == 404


async def test_a_paused_run_can_be_cancelled(
    client: AsyncClient, app: FastAPI, settings: Settings, tmp_path: Path
) -> None:
    await _setup_repo(settings, tmp_path)
    fake = _FakeClaudeCode(_replies(["Book"], []))
    app.dependency_overrides[get_claude] = lambda: fake
    try:
        response = await client.post(
            "/api/v1/runs/check-change",
            json={"mode": "mocked", "flow": "Book", "approve_plan": True},
        )
        run_id = response.json()["id"]
        await _until(client, run_id, lambda d: d["awaiting_approval"])
        cancelled = await client.post(f"/api/v1/runs/{run_id}/cancel")
        assert cancelled.status_code == 200
        await app.state.run_manager.wait()
    finally:
        del app.dependency_overrides[get_claude]

    detail = (await client.get(f"/api/v1/runs/{run_id}")).json()
    assert detail["status"] == "finished" and detail["awaiting_approval"] is False
    assert detail["verdict"] == "BLOCKED"
    assert "functionality-tester" not in fake.agents_called


async def test_skipping_every_case_blocks_the_run_instead_of_passing_it(
    client: AsyncClient, app: FastAPI, settings: Settings, tmp_path: Path
) -> None:
    await _setup_repo(settings, tmp_path)
    fake = _FakeClaudeCode(_replies(["Book"], []))
    app.dependency_overrides[get_claude] = lambda: fake
    try:
        response = await client.post(
            "/api/v1/runs/check-change",
            json={"mode": "mocked", "flow": "Book", "approve_plan": True},
        )
        run_id = response.json()["id"]
        await _until(client, run_id, lambda d: d["awaiting_approval"])
        await client.post(f"/api/v1/runs/{run_id}/approve", json={"skip": ["TC-1"]})
        await app.state.run_manager.wait()
    finally:
        del app.dependency_overrides[get_claude]

    detail = (await client.get(f"/api/v1/runs/{run_id}")).json()
    assert detail["verdict"] == "BLOCKED"
    assert "No approved test case" in detail["blocked_reason"]


async def test_pipeline_only_agents_are_not_standalone(client: AsyncClient) -> None:
    agents = {a["name"]: a for a in (await client.get("/api/v1/qa-config")).json()["agents"]}
    for name in ("qa-lead", "test-case-reviewer", "qa-reporter", "test-writer"):
        assert agents[name]["standalone"] is False
    for name in ("functionality-tester", "api-checker", "code-reviewer", "design-reviewer"):
        assert agents[name]["standalone"] is True
