"""MCP server wrapping the QA testing agent's own HTTP API, so any MCP-compatible AI coding
tool (Cursor, Antigravity, Windsurf, Claude Code, ...) can trigger Quick Scan or Check my
change and read back findings, without opening the web dashboard.

This is a thin client over the backend's REST API (see app/api/routes/) — it holds no QA logic
of its own, so there's exactly one place that decides what's safe to run (the backend, same as
the dashboard and the /qa-run Claude Code skill both already go through).

Run with: `uv run qa-mcp-server` (or `uv run python -m app.mcp_server`).
Needs the QA backend already running separately (./run-local-dev.sh from the repo root) — this
process only talks to it over HTTP, it doesn't start it.
"""

import asyncio
from typing import Any, Literal

import httpx
from mcp.server.mcpserver import MCPServer

from app.core.config import get_settings

POLL_S = 3.0
MAX_WAIT_S = 1800.0  # 30 min: generous for a multi-scenario Check my change

server = MCPServer(
    "qa-testing-agent",
    instructions=(
        "Runs this project's local QA testing agent (Quick Scan, no AI; Check my change, "
        "Claude Code on the developer's own subscription) and returns the verdict and open "
        "findings. Start the backend first with ./run-local-dev.sh if a call reports it's "
        "unreachable."
    ),
)


def _dashboard_url(run_id: str) -> str:
    return f"{get_settings().mcp_dashboard_url.rstrip('/')}/runs/{run_id}"


def _summarize(run: dict[str, Any]) -> dict[str, Any]:
    findings = [
        {
            "severity": f["severity"],
            "title": f["title"],
            "location": f["location"],
            "expected": f["expected"],
            "actual": f["actual"],
        }
        for f in run.get("findings", [])
        if f.get("status") == "open"
    ]
    return {
        "run_id": run["id"],
        "status": run["status"],
        "verdict": run.get("verdict"),
        "blocked_reason": run.get("blocked_reason"),
        "plan_summary": run.get("plan_summary"),
        "open_findings": findings,
        "dashboard_url": _dashboard_url(run["id"]),
    }


async def _poll(client: httpx.AsyncClient, base_url: str, run_id: str) -> dict[str, Any]:
    waited = 0.0
    while waited < MAX_WAIT_S:
        response = await client.get(f"{base_url}/runs/{run_id}")
        response.raise_for_status()
        run = response.json()
        if run["status"] == "finished":
            return _summarize(run)
        await asyncio.sleep(POLL_S)
        waited += POLL_S
    return {
        "run_id": run_id,
        "status": "still_running",
        "note": f"Didn't finish within {int(MAX_WAIT_S)}s; check back with get_run.",
        "dashboard_url": _dashboard_url(run_id),
    }


async def _start(
    client: httpx.AsyncClient, base_url: str, path: str, body: dict[str, Any]
) -> dict[str, Any]:
    try:
        response = await client.post(f"{base_url}/runs/{path}", json=body)
    except httpx.HTTPError as exc:
        return {
            "error": f"Can't reach the QA backend at {base_url} ({exc}). Start it first: "
            "./run-local-dev.sh from the testing_agent repo root."
        }
    if response.status_code == 412:
        return {"error": f"Agent runs are refused: {response.json().get('detail')}"}
    if response.status_code == 409:
        return {"error": f"Another run is already active: {response.json().get('detail')}"}
    response.raise_for_status()
    return await _poll(client, base_url, response.json()["id"])


@server.tool()
async def quick_scan(mode: Literal["mocked", "real"] = "mocked") -> dict[str, Any]:
    """Run Quick Scan: every configured page at desktop and mobile size, no AI, checking for
    console errors, page crashes, failed/slow API calls, broken images/links and layout
    overflow. Returns the verdict and open findings once it finishes."""
    base_url = get_settings().mcp_backend_url
    async with httpx.AsyncClient(timeout=30.0) as client:
        return await _start(client, base_url, "quick-scan", {"mode": mode})


@server.tool()
async def check_change(
    flow: str | None = None,
    mode: Literal["mocked", "real"] = "mocked",
    base_ref: str | None = None,
) -> dict[str, Any]:
    """Run Check my change: the QA Lead plans test case scenarios (the normal path plus edge
    cases) from the local git diff and/or the flow you describe, then the Functionality tester
    tests every one of them, followed by the Code/Design/API review. Works even with no local
    diff when you describe a flow — e.g. testing something already deployed. Returns the
    verdict, the planned scenarios (in plan_summary) and open findings."""
    body: dict[str, Any] = {"mode": mode}
    if flow:
        body["flow"] = flow
    if base_ref:
        body["base_ref"] = base_ref
    base_url = get_settings().mcp_backend_url
    async with httpx.AsyncClient(timeout=30.0) as client:
        return await _start(client, base_url, "check-change", body)


@server.tool()
async def get_run(run_id: str) -> dict[str, Any]:
    """Look up a run by id (from a previous quick_scan/check_change call) without starting a
    new one — useful if it was still running when that tool returned."""
    base_url = get_settings().mcp_backend_url
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{base_url}/runs/{run_id}")
        if response.status_code == 404:
            return {"error": f"No run {run_id}"}
        response.raise_for_status()
        return _summarize(response.json())


@server.tool()
async def list_open_findings() -> list[dict[str, Any]]:
    """List every open finding across recent runs (the same list as the dashboard's To review
    page) without starting a new run."""
    base_url = get_settings().mcp_backend_url
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{base_url}/findings", params={"status": "open"})
        response.raise_for_status()
        return [
            {
                "run_id": item["run_id"],
                "severity": item["severity"],
                "title": item["title"],
                "location": item["location"],
                "expected": item["expected"],
                "actual": item["actual"],
            }
            for item in response.json()
        ]


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
