from pathlib import Path

import httpx

from app.integrations.http_probe import HttpProbe
from app.schemas.qa_config import ApiChecksConfig, ApiCheckSpec, EndpointRule, QaConfig
from app.schemas.runs import RunParams
from app.services.api_checks import error_finding, label, response_findings, run_api_checks
from app.services.findings import IgnoreList
from app.services.run_manager import RunContext
from app.services.run_store import RunStore


def test_label_uses_name_or_falls_back_to_method_and_path() -> None:
    assert label(ApiCheckSpec(path="/api/pricing")) == "GET /api/pricing"
    assert label(ApiCheckSpec(path="/api/pricing", name="Pricing")) == "Pricing"


def test_response_findings_ok_status_under_the_limit_is_clean() -> None:
    spec = ApiCheckSpec(path="/api/pricing")
    assert (
        response_findings(spec, status_code=200, body="{}", duration_ms=10, slow_api_ms=2000) == []
    )


def test_response_findings_5xx_is_high_4xx_is_medium() -> None:
    spec = ApiCheckSpec(path="/api/pricing")
    high = response_findings(spec, status_code=500, body="boom", duration_ms=10, slow_api_ms=2000)
    medium = response_findings(spec, status_code=404, body="nope", duration_ms=10, slow_api_ms=2000)
    assert high[0].severity == "High" and high[0].actual == "HTTP 500"
    assert medium[0].severity == "Medium" and medium[0].actual == "HTTP 404"


def test_response_findings_respects_a_custom_expect_status() -> None:
    spec = ApiCheckSpec(path="/api/pricing", expect_status=[204])
    assert response_findings(spec, status_code=204, body="", duration_ms=10, slow_api_ms=2000) == []
    findings = response_findings(spec, status_code=200, body="", duration_ms=10, slow_api_ms=2000)
    assert findings[0].expected == "One of [204]"


def test_response_findings_slow_call_is_a_warning() -> None:
    spec = ApiCheckSpec(path="/api/pricing")
    findings = response_findings(
        spec, status_code=200, body="{}", duration_ms=5000, slow_api_ms=2000
    )
    assert findings[0].severity == "Warning"
    assert findings[0].actual == "5000 ms"


def test_error_finding_names_the_failure_without_guessing_a_status() -> None:
    spec = ApiCheckSpec(path="/api/pricing")
    finding = error_finding(spec, url="http://x/api/pricing", error="ConnectError: boom")
    assert finding.severity == "High"
    assert finding.actual == "ConnectError: boom"


def _ctx(tmp_path: Path) -> RunContext:
    store = RunStore(tmp_path, 20)
    record = store.create("quick-scan", "Quick Scan", RunParams())
    return RunContext(store, record, IgnoreList(tmp_path / "ignored.json"))


async def test_run_api_checks_does_nothing_when_none_are_configured(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    async with httpx.AsyncClient() as client:
        await run_api_checks(ctx, app_url="http://x", qa=QaConfig(), probe=HttpProbe(client))
    assert ctx.record.findings == []


async def test_run_api_checks_never_calls_a_risky_endpoint(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    called: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(str(request.url))
        return httpx.Response(200, json={})

    qa = QaConfig(
        api_checks=ApiChecksConfig(endpoints=[ApiCheckSpec(path="/api/payment-status")]),
        risky_endpoints=[EndpointRule(url="*/api/*payment*")],
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await run_api_checks(ctx, app_url="http://x", qa=qa, probe=HttpProbe(client))
    assert called == []  # never even requested
    assert ctx.record.findings == []


async def test_run_api_checks_reports_a_failing_endpoint(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    qa = QaConfig(api_checks=ApiChecksConfig(endpoints=[ApiCheckSpec(path="/api/pricing")]))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await run_api_checks(ctx, app_url="http://x", qa=qa, probe=HttpProbe(client))
    assert len(ctx.record.findings) == 1
    assert ctx.record.findings[0].severity == "High"
    assert ctx.record.findings[0].location == "API · GET /api/pricing"


async def test_run_api_checks_reports_a_connection_failure(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    qa = QaConfig(api_checks=ApiChecksConfig(endpoints=[ApiCheckSpec(path="/api/pricing")]))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await run_api_checks(ctx, app_url="http://x", qa=qa, probe=HttpProbe(client))
    assert len(ctx.record.findings) == 1
    assert ctx.record.findings[0].severity == "High"
    assert "ConnectError" in ctx.record.findings[0].actual
