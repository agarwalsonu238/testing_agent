"""Quick Scan (no AI): every configured page at every viewport; findings from fixed rules.

Severity (plan section 10):
- High: page crash / uncaught error, page or API call answering 5xx or failing, page not loading
- Medium: console error, broken image or link, 4xx page or API answer, page wider than the screen
- Warning: API call slower than `slow_api_ms`, page slower than `slow_page_ms`
"""

import contextlib
import re
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import Settings
from app.core.errors import BlockedError
from app.integrations.browser import (
    BrowserSession,
    BrowserUnavailableError,
    LoginError,
    PageObservation,
)
from app.integrations.http_probe import HttpProbe
from app.schemas.qa_config import Limits, QaConfig
from app.schemas.runs import Evidence, FailureCategory, Finding, RunMode, Severity
from app.services.api_checks import run_api_checks
from app.services.qa_config import NetworkGuard, compile_noise, route_slug
from app.services.run_manager import RunContext

AGENT = "quick-scan"
MAX_PER_KIND = 5
_BLOCKED_BY_GUARD = "ERR_BLOCKED_BY_CLIENT"
# Chrome logs every failed request to the console too; the request itself is already a finding.
BROWSER_REQUEST_ECHO = "Failed to load resource"
_ENV_ERRORS = ("ERR_CONNECTION_REFUSED", "ERR_NAME_NOT_RESOLVED", "ERR_CONNECTION_RESET")


def _is_noise(text: str, noise: list[re.Pattern[str]]) -> bool:
    return any(p.search(text) for p in noise)


def _path(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path or url


def observations_to_findings(
    obs: PageObservation,
    limits: Limits,
    noise: list[re.Pattern[str]],
    screenshot_rel: str | None = None,
) -> list[Finding]:
    """Apply the Quick Scan rules to one page at one viewport (pure; no I/O)."""
    loc = f"{obs.page_path} · {obs.viewport}"
    shot = [
        Evidence(kind="screenshot", label=f"{obs.page_name} ({obs.viewport})", path=screenshot_rel)
    ]
    shot = shot if screenshot_rel else []
    findings: list[Finding] = []

    def add(
        title: str,
        severity: Severity,
        expected: str,
        actual: str,
        category: FailureCategory = "regression",
        evidence: list[Evidence] | None = None,
    ) -> None:
        findings.append(
            Finding(
                id="",
                agent=AGENT,
                title=title,
                severity=severity,
                category=category,
                location=loc,
                expected=expected,
                actual=actual,
                evidence=(evidence or []) + shot,
            )
        )

    if obs.nav_error:
        env = any(code in obs.nav_error for code in _ENV_ERRORS)
        add(
            f"{obs.page_name} didn't load",
            "High",
            "The page loads",
            obs.nav_error,
            category="environment" if env else "regression",
        )
        return findings

    if obs.main_status is not None and obs.main_status >= 400:
        add(
            f"{obs.page_name} answered HTTP {obs.main_status}",
            "High" if obs.main_status >= 500 else "Medium",
            "HTTP 200",
            f"HTTP {obs.main_status} for {obs.url}",
        )

    for err in [e for e in obs.page_errors if not _is_noise(e, noise)][:MAX_PER_KIND]:
        first = err.strip().splitlines()[0][:160] if err.strip() else "Uncaught error"
        add(
            f"Uncaught error: {first}",
            "High",
            "No uncaught errors",
            first,
            evidence=[Evidence(kind="console", label="Page error", text=err[:2000])],
        )

    console = list(
        dict.fromkeys(
            c
            for c in obs.console_errors
            if not _is_noise(c, noise) and not c.startswith(BROWSER_REQUEST_ECHO)
        )
    )
    for msg in console[:MAX_PER_KIND]:
        add(
            f"Console error: {msg.strip().splitlines()[0][:160]}",
            "Medium",
            "No console errors",
            msg[:300],
            evidence=[Evidence(kind="console", label="Console", text=msg[:2000])],
        )

    for req in obs.requests:
        if _is_noise(req.url, noise):
            continue
        where = f"{req.method} {_path(req.url)}"
        net = [Evidence(kind="network", label="Request", text=f"{req.method} {req.url}")]
        if req.failure:
            if _BLOCKED_BY_GUARD in req.failure:
                continue  # our own risky-endpoint block, reported as an event
            add(f"API call failed: {where}", "High", "A response", req.failure, evidence=net)
        elif req.status is not None and req.status >= 400:
            add(
                f"API call answered {req.status}: {where}",
                "High" if req.status >= 500 else "Medium",
                "HTTP 2xx/3xx",
                f"HTTP {req.status}",
                evidence=net,
            )
        elif req.duration_ms is not None and req.duration_ms > limits.slow_api_ms:
            add(
                f"Slow API call: {where}",
                "Warning",
                f"Under {limits.slow_api_ms} ms",
                f"{req.duration_ms:.0f} ms",
                evidence=net,
            )

    for src in obs.broken_images[:MAX_PER_KIND]:
        add(f"Broken image: {_path(src)}", "Medium", "The image loads", f"{src} didn't load")

    for link, status in obs.broken_links[:MAX_PER_KIND]:
        add(f"Broken link: {_path(link)}", "Medium", "The link opens", f"{link} → {status}")

    if obs.overflow_px > 1:
        mobile = obs.viewport == "mobile"
        add(
            "Page is wider than a phone screen" if mobile else "Page scrolls sideways",
            "Medium",
            "No horizontal scrolling",
            f"Content is {obs.overflow_px}px wider than the {obs.viewport} viewport",
        )

    if obs.load_ms is not None and obs.load_ms > limits.slow_page_ms:
        add(
            f"Slow page: {obs.page_name}",
            "Warning",
            f"Loads in under {limits.slow_page_ms} ms",
            f"{obs.load_ms:.0f} ms",
        )
    return findings


async def prepare_storage_state(
    session: BrowserSession,
    *,
    settings: Settings,
    qa: QaConfig,
    mode: RunMode,
    guard: NetworkGuard,
    out: Path,
) -> Path | None:
    """Mock login (storage state from the app repo) or real login with the shared test account.

    Raises BlockedError when the login is configured but fails.
    """
    if mode == "mocked":
        rel = qa.auth.mock_storage_state
        if rel and settings.app_repo_path:
            path = settings.app_repo_path / rel
            if not path.is_file():
                raise BlockedError(f"Mock login file {path} doesn't exist")
            return path
        return None
    form = qa.auth.login
    if form is None:
        return None
    password = settings.test_account_password
    if not settings.test_account_email or not (password and password.get_secret_value()):
        raise BlockedError(
            "Real-backend mode needs TEST_ACCOUNT_EMAIL and TEST_ACCOUNT_PASSWORD in .env"
        )
    try:
        await session.login(
            base_url=settings.app_url,
            path=form.path,
            email_selector=form.email_selector,
            password_selector=form.password_selector,
            submit_selector=form.submit_selector,
            success_url=form.success_url,
            email=settings.test_account_email,
            password=password.get_secret_value(),
            decide=guard.decide,
            storage_state_out=out,
            timeout_ms=qa.limits.page_timeout_ms,
        )
    except LoginError as exc:
        raise BlockedError(f"The test login failed: {exc}") from exc
    return out


async def run_quick_scan(
    ctx: RunContext, *, settings: Settings, qa: QaConfig, mode: RunMode, probe: HttpProbe
) -> None:
    """Scan every page at every viewport. Raises BlockedError if the app/browser isn't ready."""
    reachable, detail = await probe.reachable(settings.app_url)
    if not reachable:
        raise BlockedError(f"The app isn't running at {settings.app_url} ({detail})")
    guard = NetworkGuard(qa, mode)
    noise = compile_noise(qa.noise_filter)
    shots = ctx.dir / "screenshots"
    traces = ctx.dir / "traces"
    shots.mkdir(exist_ok=True)
    traces.mkdir(exist_ok=True)
    auth_state = ctx.dir / ".auth-state.json"

    def on_blocked(what: str) -> None:
        ctx.event(f"Blocked {what}", level="warn", source=AGENT)

    try:
        async with BrowserSession(settings.browser_channel, settings.browser_headless) as session:
            ctx.event(
                f"Browser {session.version}; {mode} mode; {len(qa.pages)} pages", source=AGENT
            )
            state = await prepare_storage_state(
                session, settings=settings, qa=qa, mode=mode, guard=guard, out=auth_state
            )
            for vp_name, vp in qa.viewports.items():
                context = await session.new_context(
                    width=vp.width,
                    height=vp.height,
                    is_mobile=vp.is_mobile,
                    decide=guard.decide,
                    on_blocked=on_blocked,
                    storage_state=state,
                )
                trace_path = traces / f"trace-{vp_name}.zip"
                try:
                    for page in qa.pages:
                        ctx.event(f"Scanning {page.path} at {vp_name} size", source=AGENT)
                        shot = shots / f"{route_slug(page.path)}-{vp_name}.png"
                        obs = await session.scan_page(
                            context,
                            base_url=settings.app_url,
                            page_path=page.path,
                            page_name=page.name,
                            viewport=vp_name,
                            screenshot_path=shot,
                            timeout_ms=qa.limits.page_timeout_ms,
                            max_links=qa.limits.max_links_per_page,
                            api_pattern=qa.api_url_pattern,
                            decide=guard.decide,
                        )
                        rel = ctx.rel(shot) if obs.screenshot else None
                        if rel:
                            ctx.add_artifact(f"{page.name} · {vp_name}", shot, "screenshot")
                        found = observations_to_findings(obs, qa.limits, noise, rel)
                        ctx.add_findings(found)
                        ctx.event(
                            f"{page.path} at {vp_name}: {len(found)} finding(s)",
                            level="warn" if found else "info",
                            source=AGENT,
                        )
                finally:
                    await session.close_context(context, trace_path)
                    if trace_path.exists():
                        ctx.add_artifact(f"Playwright trace ({vp_name})", trace_path, "trace")
    except BrowserUnavailableError as exc:
        raise BlockedError(f"The browser couldn't start: {exc}") from exc
    finally:
        with contextlib.suppress(FileNotFoundError):
            auth_state.unlink()  # session cookies don't stay on disk

    await run_api_checks(ctx, app_url=settings.app_url, qa=qa, probe=probe)
