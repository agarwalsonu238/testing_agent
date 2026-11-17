from datetime import UTC, datetime

from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import SecretStr

from app.core.config import Settings
from app.schemas.runs import AgentResult, Finding, RunParams
from app.services.run_manager import RunManager


async def _wait(app: FastAPI) -> None:
    manager: RunManager = app.state.run_manager
    await manager.wait()


def _seed_run(app: FastAPI, *, flow_passed: bool = False) -> str:
    manager: RunManager = app.state.run_manager
    record = manager.store.create("agent", "functionality-tester", RunParams())
    record.status = "finished"
    record.verdict = "FAILING"
    record.finished_at = datetime.now(UTC)
    record.findings = [
        Finding(
            id="f1",
            agent="quick-scan",
            title="Console error: boom",
            severity="Medium",
            category="regression",
            location="/ · mobile",
        )
    ]
    if flow_passed:
        record.agents = [
            AgentResult(agent="functionality-tester", task="1. Open /", verdict="PASS")
        ]
    manager.store.save(record)
    return record.id


async def test_quick_scan_is_blocked_when_the_app_is_not_running(
    client: AsyncClient, app: FastAPI
) -> None:
    response = await client.post("/api/v1/runs/quick-scan", json={"mode": "mocked"})
    assert response.status_code == 202
    run = response.json()
    assert run["kind"] == "quick-scan" and run["status"] == "running"

    await _wait(app)
    detail = (await client.get(f"/api/v1/runs/{run['id']}")).json()
    assert detail["status"] == "finished"
    assert detail["verdict"] == "BLOCKED"
    assert "isn't running" in detail["blocked_reason"]
    assert detail["report_summary"].startswith("**QA agent: BLOCKED**")

    events = (await client.get(f"/api/v1/runs/{run['id']}/events?after=0")).json()
    assert events["done"] is True
    assert [e["seq"] for e in events["events"]] == list(range(1, len(events["events"]) + 1))

    listed = (await client.get("/api/v1/runs")).json()
    assert listed[0]["id"] == run["id"] and listed[0]["counts"] == {"open": 0, "total": 0}


async def test_unknown_run_and_bad_ids_are_404_or_422(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/runs/20250101-000000-quick-scan-abcdef")).status_code == 404
    assert (await client.get("/api/v1/runs/..%2Fetc")).status_code in (404, 422)


async def test_run_files_cannot_escape_the_run_folder(client: AsyncClient, app: FastAPI) -> None:
    run_id = _seed_run(app)
    assert (await client.get(f"/api/v1/runs/{run_id}/files/run.json")).status_code == 200
    escaped = await client.get(f"/api/v1/runs/{run_id}/files/..%2F..%2Fignored.json")
    assert escaped.status_code == 404


async def test_ignore_needs_a_reason_and_is_remembered(client: AsyncClient, app: FastAPI) -> None:
    run_id = _seed_run(app)
    url = f"/api/v1/runs/{run_id}/findings/f1/decision"

    no_reason = await client.post(url, json={"decision": "ignore"})
    assert no_reason.status_code == 422

    ignored = await client.post(url, json={"decision": "ignore", "reason": "Known widget bug"})
    assert ignored.status_code == 200
    assert ignored.json()["status"] == "ignored"
    assert ignored.json()["ignore_reason"] == "Known widget bug"

    assert (await client.get("/api/v1/findings?status=open")).json() == []
    items = (await client.get("/api/v1/findings?status=ignored")).json()
    assert items[0]["run_id"] == run_id and items[0]["fingerprint"]

    accepted = await client.post(url, json={"decision": "accept"})
    assert accepted.json()["status"] == "accepted"
    missing = await client.post(
        f"/api/v1/runs/{run_id}/findings/f99/decision", json={"decision": "accept"}
    )
    assert missing.status_code == 404


async def test_save_as_test_needs_a_passing_flow(client: AsyncClient, app: FastAPI) -> None:
    failing = _seed_run(app)
    response = await client.post(f"/api/v1/runs/{failing}/save-test", json={})
    assert response.status_code == 409

    passing = _seed_run(app, flow_passed=True)
    detail = (await client.get(f"/api/v1/runs/{passing}")).json()
    assert detail["can_save_as_test"] is True


async def test_agent_runs_are_refused_while_an_api_key_is_set(
    client: AsyncClient, settings: Settings
) -> None:
    settings.anthropic_api_key = SecretStr("sk-ant-test")
    response = await client.post(
        "/api/v1/runs/agent", json={"agent": "code-reviewer", "task": "Review it"}
    )
    assert response.status_code == 412
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]
    assert "sk-ant-test" not in response.text


async def test_unknown_agent_is_404_and_invalid_body_is_422(client: AsyncClient) -> None:
    unknown = await client.post(
        "/api/v1/runs/agent", json={"agent": "no-such-agent", "task": "x y z"}
    )
    assert unknown.status_code == 404
    bad = await client.post("/api/v1/runs/agent", json={"agent": "Bad Name", "task": "x"})
    assert bad.status_code == 422


async def test_cancel_a_finished_run_is_409(client: AsyncClient, app: FastAPI) -> None:
    run_id = _seed_run(app)
    assert (await client.post(f"/api/v1/runs/{run_id}/cancel")).status_code == 409


async def test_qa_config_lists_agents_and_pages(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/qa-config")).json()
    assert {a["name"] for a in body["agents"]} >= {"qa-lead", "code-reviewer"}
    assert body["pages"] == ["/"]
    assert body["viewports"] == ["desktop", "mobile"]


async def test_saved_tests_need_an_app_repo(client: AsyncClient) -> None:
    response = await client.get("/api/v1/saved-tests")
    assert response.status_code == 412
