"""API checks (no AI, no browser): call each endpoint in `qa.api_checks.endpoints` directly and
report status-code/latency problems, the same severities Quick Scan uses for API calls it
observes during a page visit.

GET-only, and `risky_endpoints` is always honoured, even for an endpoint that isn't itself
flagged as risky but matches a risky glob (e.g. `*/api/*payment*`): this is the only kind of
check in the whole agent that can hit the real backend with no browser, no mocks and no login
session in front of it, so it never calls anything the config says is off-limits.
"""

import time

import httpx

from app.integrations.http_probe import HttpProbe
from app.schemas.qa_config import ApiCheckSpec, QaConfig
from app.schemas.runs import Evidence, Finding
from app.services.qa_config import rule_matches
from app.services.run_manager import RunContext

AGENT = "quick-scan"


def label(spec: ApiCheckSpec) -> str:
    return spec.name or f"{spec.method} {spec.path}"


def response_findings(
    spec: ApiCheckSpec, *, status_code: int, body: str, duration_ms: float, slow_api_ms: int
) -> list[Finding]:
    """Pure: the findings (if any) for one answered call."""
    loc = f"API · {label(spec)}"
    ok_statuses = spec.expect_status or list(range(200, 400))
    if status_code not in ok_statuses:
        return [
            Finding(
                id="",
                agent=AGENT,
                title=f"API answered {status_code}: {label(spec)}",
                severity="High" if status_code >= 500 else "Medium",
                category="regression",
                location=loc,
                expected=(f"One of {ok_statuses}" if spec.expect_status else "HTTP 2xx/3xx"),
                actual=f"HTTP {status_code}",
                evidence=[Evidence(kind="network", label="Response body", text=body[:2000])],
            )
        ]
    if duration_ms > slow_api_ms:
        return [
            Finding(
                id="",
                agent=AGENT,
                title=f"Slow API call: {label(spec)}",
                severity="Warning",
                category="regression",
                location=loc,
                expected=f"Under {slow_api_ms} ms",
                actual=f"{duration_ms:.0f} ms",
            )
        ]
    return []


def error_finding(spec: ApiCheckSpec, *, url: str, error: str) -> Finding:
    return Finding(
        id="",
        agent=AGENT,
        title=f"API call failed: {label(spec)}",
        severity="High",
        category="regression",
        location=f"API · {label(spec)}",
        expected="A response",
        actual=error,
        evidence=[Evidence(kind="network", label="Request", text=url)],
    )


async def run_api_checks(ctx: RunContext, *, app_url: str, qa: QaConfig, probe: HttpProbe) -> None:
    specs = qa.api_checks.endpoints
    if not specs:
        return
    ctx.event(f"Checking {len(specs)} API endpoint(s)", source=AGENT)
    for spec in specs:
        url = f"{app_url.rstrip('/')}{spec.path}"
        if any(rule_matches(r, url, spec.method) for r in qa.risky_endpoints):
            ctx.event(
                f"Skipped {label(spec)}: matches a risky endpoint", level="warn", source=AGENT
            )
            continue

        started = time.monotonic()
        try:
            response = await probe.get(url, headers=spec.headers or None)
        except httpx.HTTPError as exc:
            ctx.add_findings([error_finding(spec, url=url, error=f"{type(exc).__name__}: {exc}")])
            ctx.event(f"{label(spec)}: no response ({exc})", level="warn", source=AGENT)
            continue

        duration_ms = (time.monotonic() - started) * 1000
        findings = response_findings(
            spec,
            status_code=response.status_code,
            body=response.text,
            duration_ms=duration_ms,
            slow_api_ms=qa.limits.slow_api_ms,
        )
        ctx.add_findings(findings)
        ctx.event(
            f"{label(spec)}: HTTP {response.status_code} ({duration_ms:.0f} ms)",
            level="warn" if findings else "info",
            source=AGENT,
        )
