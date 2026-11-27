import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import SecretStr

from app.api.deps import get_claude
from app.core.config import Settings, get_settings
from app.integrations import git
from app.integrations.claude_code import AgentInvocation, ClaudeRunResult, ProgressFn
from app.schemas.runs import AgentResult, Finding, RunParams
from app.services.agents import QA_LEAD
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


class _FakeClaudeCode:
    """Stands in for the `claude` binary: returns a canned structured reply per agent name."""

    def __init__(self, replies: dict[str, dict[str, Any]]) -> None:
        self._replies = replies
        self.agents_called: list[str] = []
        self.invocations: list[AgentInvocation] = []

    def ensure_no_billed_credentials(self) -> None:
        return None

    async def run(
        self, inv: AgentInvocation, on_progress: ProgressFn, timeout_s: float | None = None
    ) -> ClaudeRunResult:
        self.agents_called.append(inv.agent)
        self.invocations.append(inv)
        return ClaudeRunResult(ok=True, structured=self._replies.get(inv.agent, {}))


async def _init_repo_with_no_pending_changes(path: Path) -> None:
    """A real, committed git repo with nothing changed — `git diff` against it is empty."""
    await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)
    await git.git(path, "init", "-q")
    await git.git(path, "config", "user.email", "qa@test.local")
    await git.git(path, "config", "user.name", "QA Test")
    await asyncio.to_thread((path / "README.md").write_text, "placeholder")
    await git.commit(path, ["README.md"], "initial")


async def test_check_change_tests_a_described_flow_even_with_no_diff(
    client: AsyncClient, app: FastAPI, settings: Settings, tmp_path: Path
) -> None:
    """Regression: the developer's flow must still be tested when there's nothing to diff
    against (e.g. checking an already-deployed change) — it must never be silently skipped."""
    settings.app_repo_path = tmp_path / "app-repo"
    await _init_repo_with_no_pending_changes(settings.app_repo_path)
    fake = _FakeClaudeCode(
        {
            "qa-lead": {
                "summary": "No diff; testing the described flow.",
                "design_routes": [],
                "scenarios": [
                    "1. Book the same pet for the same date twice.\nExpected: the first "
                    "booking is cancelled.",
                    "2. Book a different pet for the same date.\nExpected: both bookings "
                    "stay active.",
                ],
            },
            "functionality-tester": {"case_observations": [], "steps": []},
            "qa-reporter": {"summary": "Checked.", "findings": [], "steps": []},
        }
    )
    app.dependency_overrides[get_claude] = lambda: fake
    try:
        response = await client.post(
            "/api/v1/runs/check-change",
            json={"mode": "mocked", "flow": "Check the double-booking cancellation flow"},
        )
        assert response.status_code == 202
        run_id = response.json()["id"]
        await _wait(app)
    finally:
        del app.dependency_overrides[get_claude]

    detail = (await client.get(f"/api/v1/runs/{run_id}")).json()
    # No structured test_cases from the Lead (only free-text scenarios), so the reviewer is
    # skipped; every executor runs first (stage 3), and only then does each reporter (stage 4).
    assert fake.agents_called == [
        "qa-lead",
        "functionality-tester",
        "functionality-tester",
        "qa-reporter",
        "qa-reporter",
    ]
    assert detail["stage"] == "done"
    assert "Test cases (2), planned before testing" in detail["plan_summary"]
    assert [c["id"] for c in detail["test_cases"]] == ["TC-1", "TC-2"]
    assert len(detail["agents"]) == 2
    assert all(a["agent"] == "functionality-tester" for a in detail["agents"])
    assert "test case 1 of 2" in detail["agents"][0]["task"].lower()
    assert "test case 2 of 2" in detail["agents"][1]["task"].lower()

    # The flow text the developer typed is for the Writer (qa-lead) alone — never the executor
    # or the reporter.
    flow_text = "Check the double-booking cancellation flow"
    for inv in fake.invocations:
        if inv.agent != QA_LEAD:
            assert flow_text not in inv.prompt, f"{inv.agent}'s prompt mentions the flow text"


async def test_check_change_with_nothing_to_check_runs_no_agents(
    client: AsyncClient, app: FastAPI, settings: Settings, tmp_path: Path
) -> None:
    """No diff and no described flow: still nothing to check, and no agent is invoked."""
    settings.app_repo_path = tmp_path / "app-repo"
    await _init_repo_with_no_pending_changes(settings.app_repo_path)
    fake = _FakeClaudeCode({})
    app.dependency_overrides[get_claude] = lambda: fake
    try:
        response = await client.post("/api/v1/runs/check-change", json={"mode": "mocked"})
        run_id = response.json()["id"]
        await _wait(app)
    finally:
        del app.dependency_overrides[get_claude]

    detail = (await client.get(f"/api/v1/runs/{run_id}")).json()
    assert fake.agents_called == []
    assert detail["agents"] == []
    assert "nothing to check" in detail["plan_summary"]


async def test_check_change_never_lets_the_diff_reach_anyone_but_the_lead(
    client: AsyncClient, app: FastAPI, settings: Settings, tmp_path: Path
) -> None:
    """Only the Writer (qa-lead) may see diff.patch: every other call's `add_dirs` must not
    reach it and its prompt must not mention it. A case the reviewer rejects must never reach
    an executor."""
    settings.app_repo_path = tmp_path / "app-repo"
    await _init_repo_with_no_pending_changes(settings.app_repo_path)
    await asyncio.to_thread(
        (settings.app_repo_path / "api.py").write_text, "def handler():\n    return 1\n"
    )
    fake = _FakeClaudeCode(
        {
            "qa-lead": {
                "summary": "Logic change.",
                "design_routes": [],
                "test_cases": [
                    {
                        "title": "Handler returns 1",
                        "agent": "functionality-tester",
                        "steps": ["1. Call the handler."],
                        "expected": "Returns 1",
                    },
                    {
                        "title": "Vague edge case",
                        "agent": "functionality-tester",
                        "steps": ["Make sure it's robust"],
                        "expected": "it works",
                    },
                    {
                        "title": "api.py:1",
                        "agent": "code-reviewer",
                        "steps": ["def handler(): return 1"],
                        "expected": "Handler always returns 1",
                    },
                ],
            },
            "test-case-reviewer": {
                "cases": [
                    {
                        "title": "Handler returns 1",
                        "agent": "functionality-tester",
                        "steps": ["1. Call the handler."],
                        "expected": "Returns 1",
                        "review_status": "approved",
                    },
                    {
                        "title": "Vague edge case",
                        "agent": "functionality-tester",
                        "steps": ["Make sure it's robust"],
                        "expected": "it works",
                        "review_status": "rejected",
                        "review_note": "Not a concrete step or a falsifiable expected result",
                    },
                    {
                        "title": "api.py:1",
                        "agent": "code-reviewer",
                        "steps": ["def handler(): return 1"],
                        "expected": "Handler always returns 1",
                        "review_status": "approved",
                    },
                ],
            },
            "functionality-tester": {"case_observations": [], "steps": []},
            "code-reviewer": {"case_observations": [], "steps": []},
            "api-checker": {"case_observations": [], "steps": []},
            "qa-reporter": {
                "summary": "Checked.",
                "findings": [],
                "steps": [],
                "case_results": [{"id": "TC-1", "status": "pass"}],
            },
        }
    )
    app.dependency_overrides[get_claude] = lambda: fake
    try:
        response = await client.post("/api/v1/runs/check-change", json={"mode": "mocked"})
        run_id = response.json()["id"]
        await _wait(app)
    finally:
        del app.dependency_overrides[get_claude]

    detail = (await client.get(f"/api/v1/runs/{run_id}")).json()

    # The rejected case is skipped from the start (TC-1 is the approved one), so only one
    # functionality-tester call runs.
    cases_by_title = {c["title"]: c for c in detail["test_cases"]}
    assert cases_by_title["Vague edge case"]["status"] == "skipped"
    assert cases_by_title["Vague edge case"]["note"] == (
        "Not a concrete step or a falsifiable expected result"
    )
    assert cases_by_title["Handler returns 1"]["status"] == "pass"
    assert fake.agents_called.count("functionality-tester") == 1

    for inv in fake.invocations:
        if inv.agent == "qa-lead":
            continue  # the only role allowed to see diff.patch
        assert not any((d / "diff.patch").exists() for d in inv.add_dirs), (
            f"{inv.agent}'s add_dirs can reach diff.patch: {inv.add_dirs}"
        )
        assert "diff.patch" not in inv.prompt, f"{inv.agent}'s prompt mentions diff.patch"


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
    assert body["pages"] == []  # the tool's defaults list no pages: Quick Scan discovers them
    assert body["viewports"] == ["desktop", "mobile"]


async def test_saved_tests_need_an_app_repo(client: AsyncClient) -> None:
    response = await client.get("/api/v1/saved-tests")
    assert response.status_code == 412


async def test_single_agent_plans_and_stores_test_cases_before_running(
    client: AsyncClient, app: FastAPI, settings: Settings, tmp_path: Path
) -> None:
    """Every agent run: the QA Lead writes all test cases first (saved in test-cases.json),
    then the agent runs them and its per-case results land on the cases."""
    settings.app_repo_path = tmp_path / "app-repo"
    await _init_repo_with_no_pending_changes(settings.app_repo_path)
    fake = _FakeClaudeCode(
        {
            "qa-lead": {
                "summary": "API checks",
                "design_routes": [],
                "test_cases": [
                    {
                        "title": "List products",
                        "agent": "api-checker",
                        "steps": ["GET /api/v1/products"],
                        "expected": "200 and a list",
                    },
                    {
                        "title": "Bad page number",
                        "agent": "api-checker",
                        "steps": ["GET /api/v1/products?page=-1"],
                        "expected": "400 or 422",
                    },
                ],
            },
            "test-case-reviewer": {
                "cases": [
                    {
                        "title": "List products",
                        "agent": "api-checker",
                        "steps": ["GET /api/v1/products"],
                        "expected": "200 and a list",
                        "review_status": "approved",
                    },
                    {
                        "title": "Bad page number",
                        "agent": "api-checker",
                        "steps": ["GET /api/v1/products?page=-1"],
                        "expected": "400 or 422",
                        "review_status": "approved",
                    },
                ],
            },
            "api-checker": {
                "case_observations": [
                    {
                        "id": "TC-1",
                        "status": "pass",
                        "observed": "GET /api/v1/products returned 200 with a list",
                    }
                ],
                "steps": [],
            },
            "qa-reporter": {
                "summary": "Checked.",
                "findings": [],
                "case_results": [{"id": "TC-1", "status": "pass"}],
            },
        }
    )
    app.dependency_overrides[get_claude] = lambda: fake
    try:
        response = await client.post(
            "/api/v1/runs/agent",
            json={"agent": "api-checker", "task": "Test the products API", "mode": "real"},
        )
        assert response.status_code == 202
        run_id = response.json()["id"]
        await _wait(app)
    finally:
        del app.dependency_overrides[get_claude]

    detail = (await client.get(f"/api/v1/runs/{run_id}")).json()
    # Planning always comes first: the Lead writes cases, the Reviewer tightens or rejects them,
    # then the executor runs them and the Reporter writes up the result.
    assert fake.agents_called == ["qa-lead", "test-case-reviewer", "api-checker", "qa-reporter"]
    assert [(c["id"], c["status"]) for c in detail["test_cases"]] == [
        ("TC-1", "pass"),
        ("TC-2", "skipped"),  # the agent never reported it
    ]
    assert any(a["path"] == "test-cases.json" for a in detail["artifacts"])


async def test_qa_config_hides_a_default_folder_that_does_not_exist(
    client: AsyncClient, app: FastAPI, settings: Settings, tmp_path: Path
) -> None:
    missing = settings.model_copy(update={"app_repo_path": tmp_path / "nope"})
    app.dependency_overrides[get_settings] = lambda: missing
    assert (await client.get("/api/v1/qa-config")).json()["app_repo_path"] is None

    real = settings.model_copy(update={"app_repo_path": tmp_path})
    app.dependency_overrides[get_settings] = lambda: real
    assert (await client.get("/api/v1/qa-config")).json()["app_repo_path"] == str(tmp_path)
