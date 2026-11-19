"""Playwright (Python) wrapper: open pages, collect raw observations, log in, record traces.

It records what happened; deciding what counts as a bug is `services/quick_scan.py`'s job.
"""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from types import TracebackType
from typing import Literal, Self
from urllib.parse import urljoin, urlparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    Playwright,
    Request,
    Route,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

_SKIP_LINK = ("mailto:", "tel:", "javascript:", "#")
_SKIP_LINK_PATH = ("logout", "log-out", "signout", "sign-out")

_SCROLL_JS = """async () => {
  for (let i = 0; i < 40; i++) {
    const before = window.scrollY;
    window.scrollBy(0, Math.max(200, window.innerHeight * 0.8));
    await new Promise(r => setTimeout(r, 150));
    if (window.scrollY === before) break;
  }
}"""
_BROKEN_IMAGES_JS = """() => Array.from(document.images)
  .filter(i => i.complete && i.naturalWidth === 0 && (i.currentSrc || i.src))
  .map(i => i.currentSrc || i.src)"""
_OVERFLOW_JS = "() => document.documentElement.scrollWidth - window.innerWidth"
_LOAD_MS_JS = """() => { const n = performance.getEntriesByType('navigation')[0];
  return n && n.loadEventEnd > 0 ? n.loadEventEnd : null; }"""
_LINKS_JS = "() => Array.from(document.querySelectorAll('a[href]')).map(a => a.href)"


class BrowserUnavailableError(Exception):
    """The browser can't be started (not installed, unsupported OS, driver problem)."""


class LoginError(Exception):
    pass


@dataclass(frozen=True)
class RouteDecision:
    kind: Literal["mock", "block"]
    label: str
    status: int = 200
    body: str = ""
    headers: dict[str, str] = field(default_factory=dict)


Decide = Callable[[str, str], RouteDecision | None]  # (url, method) -> decision


@dataclass
class RequestRecord:
    url: str
    method: str
    resource_type: str
    status: int | None = None
    failure: str | None = None
    duration_ms: float | None = None


@dataclass
class PageObservation:
    page_path: str
    page_name: str
    viewport: str
    url: str
    nav_error: str | None = None
    main_status: int | None = None
    load_ms: float | None = None
    console_errors: list[str] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    requests: list[RequestRecord] = field(default_factory=list)
    broken_images: list[str] = field(default_factory=list)
    broken_links: list[tuple[str, str]] = field(default_factory=list)  # (url, status or error)
    overflow_px: int = 0
    screenshot: Path | None = None
    blocked: list[str] = field(default_factory=list)


def url_glob_match(url: str, pattern: str) -> bool:
    """`*` matches any run of characters including `/` (so `*/api/*` matches any API URL)."""
    return fnmatchcase(url, pattern.replace("**", "*"))


class BrowserSession:
    """`async with BrowserSession(channel, headless) as session:` — one browser per run."""

    def __init__(self, channel: str = "", headless: bool = True) -> None:
        self._channel = channel or None
        self._headless = headless
        self._pw: Playwright | None = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> Self:
        try:
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(
                channel=self._channel, headless=self._headless
            )
        except Exception as exc:  # driver/launch failures surface as several exception types
            await self.__aexit__(None, None, None)
            first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else repr(exc)
            raise BrowserUnavailableError(first_line[:300]) from exc
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None

    @property
    def version(self) -> str:
        return self._browser.version if self._browser else ""

    async def new_context(
        self,
        *,
        width: int,
        height: int,
        is_mobile: bool,
        decide: Decide,
        on_blocked: Callable[[str], None],
        storage_state: Path | None = None,
        trace: bool = True,
    ) -> BrowserContext:
        assert self._browser is not None  # noqa: S101 - used inside `async with`
        context = await self._browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=is_mobile,
            has_touch=is_mobile,
            device_scale_factor=2 if is_mobile else 1,
            storage_state=str(storage_state) if storage_state else None,
        )

        async def handle(route: Route) -> None:
            req = route.request
            decision = decide(req.url, req.method)
            if decision is None:
                await route.fallback()
            elif decision.kind == "mock":
                await route.fulfill(
                    status=decision.status, body=decision.body, headers=decision.headers
                )
            else:
                on_blocked(f"{req.method} {req.url} ({decision.label})")
                await route.abort("blockedbyclient")

        await context.route("**/*", handle)
        if trace:
            await context.tracing.start(screenshots=True, snapshots=True)
        return context

    @staticmethod
    async def close_context(context: BrowserContext, trace_path: Path | None) -> None:
        try:
            if trace_path is not None:
                await context.tracing.stop(path=str(trace_path))
        finally:
            await context.close()

    async def login(
        self,
        *,
        base_url: str,
        path: str,
        email_selector: str,
        password_selector: str,
        submit_selector: str,
        success_url: str,
        email: str,
        password: str,
        decide: Decide,
        storage_state_out: Path,
        timeout_ms: int,
    ) -> None:
        """Log in with the shared test account and save the session for later contexts/agents."""
        context = await self.new_context(
            width=1280,
            height=800,
            is_mobile=False,
            decide=decide,
            on_blocked=lambda _: None,
            trace=False,
        )
        try:
            page = await context.new_page()
            await page.goto(urljoin(base_url, path), timeout=timeout_ms)
            await page.fill(email_selector, email, timeout=timeout_ms)
            await page.fill(password_selector, password, timeout=timeout_ms)
            await page.click(submit_selector, timeout=timeout_ms)
            await page.wait_for_url(lambda u: url_glob_match(u, success_url), timeout=timeout_ms)
            await context.storage_state(path=str(storage_state_out))
        except PlaywrightError as exc:
            raise LoginError(str(exc).splitlines()[0][:300]) from exc
        finally:
            await context.close()

    async def scan_page(
        self,
        context: BrowserContext,
        *,
        base_url: str,
        page_path: str,
        page_name: str,
        viewport: str,
        screenshot_path: Path,
        timeout_ms: int,
        max_links: int,
        api_pattern: str,
        decide: Decide,
    ) -> PageObservation:
        url = urljoin(base_url, page_path)
        obs = PageObservation(page_path=page_path, page_name=page_name, viewport=viewport, url=url)
        page = await context.new_page()

        def on_console(msg: ConsoleMessage) -> None:
            if msg.type == "error":
                obs.console_errors.append(msg.text)

        def is_api(req: Request) -> bool:
            return req.resource_type in ("fetch", "xhr") or url_glob_match(req.url, api_pattern)

        async def on_finished(req: Request) -> None:
            if not is_api(req):
                return
            response = await req.response()
            timing = req.timing
            duration = timing.get("responseEnd", -1)
            obs.requests.append(
                RequestRecord(
                    url=req.url,
                    method=req.method,
                    resource_type=req.resource_type,
                    status=response.status if response else None,
                    duration_ms=duration if duration and duration > 0 else None,
                )
            )

        def on_failed(req: Request) -> None:
            if is_api(req):
                obs.requests.append(
                    RequestRecord(
                        url=req.url,
                        method=req.method,
                        resource_type=req.resource_type,
                        failure=req.failure or "failed",
                    )
                )

        page.on("console", on_console)
        page.on("pageerror", lambda err: obs.page_errors.append(str(err)))
        page.on("requestfinished", on_finished)
        page.on("requestfailed", on_failed)

        started = time.monotonic()
        try:
            response = await page.goto(url, wait_until="load", timeout=timeout_ms)
            obs.main_status = response.status if response else None
            obs.load_ms = (time.monotonic() - started) * 1000
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except PlaywrightTimeout:
                pass  # long-polling apps never go idle; the page has loaded
            nav_ms = await page.evaluate(_LOAD_MS_JS)
            if isinstance(nav_ms, int | float):
                obs.load_ms = float(nav_ms)
            await page.evaluate(_SCROLL_JS)
            await page.wait_for_timeout(500)
            obs.broken_images = list(await page.evaluate(_BROKEN_IMAGES_JS))
            obs.overflow_px = int(await page.evaluate(_OVERFLOW_JS))
            await page.screenshot(path=str(screenshot_path), full_page=True)
            obs.screenshot = screenshot_path
            links = await page.evaluate(_LINKS_JS)
            obs.broken_links = await self._check_links(
                context, base_url, list(links), max_links, decide
            )
        except PlaywrightError as exc:
            obs.nav_error = str(exc).strip().splitlines()[0][:300]
        finally:
            await page.close()
        return obs

    @staticmethod
    async def _check_links(
        context: BrowserContext, base_url: str, links: list[str], limit: int, decide: Decide
    ) -> list[tuple[str, str]]:
        origin = urlparse(base_url).netloc
        seen: list[str] = []
        for href in links:
            clean = href.split("#")[0]
            parsed = urlparse(clean)
            if (
                not clean
                or href.startswith(_SKIP_LINK)
                or parsed.netloc != origin
                or any(s in parsed.path.lower() for s in _SKIP_LINK_PATH)
                or decide(clean, "GET") is not None
                or clean in seen
            ):
                continue
            seen.append(clean)
            if len(seen) >= limit:
                break
        broken: list[tuple[str, str]] = []
        for link in seen:
            try:
                resp = await context.request.get(link, timeout=10000, max_redirects=5)
                if resp.status >= 400:
                    broken.append((link, str(resp.status)))
                await resp.dispose()
            except PlaywrightError as exc:
                broken.append((link, str(exc).splitlines()[0][:120]))
        return broken


def mock_body(json_body: object, body: str | None) -> tuple[str, dict[str, str]]:
    if body is not None:
        return body, {}
    return json.dumps(json_body), {"content-type": "application/json"}


async def probe_browser(channel: str, headless: bool) -> str:
    """Start and stop the browser. Returns its version; raises BrowserUnavailableError."""
    async with BrowserSession(channel, headless) as session:
        return session.version
