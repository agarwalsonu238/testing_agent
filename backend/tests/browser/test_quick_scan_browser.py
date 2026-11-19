"""Quick Scan against a local site with planted bugs (plan phase 1 "done when").

Needs a working browser; skipped otherwise. On macOS 12 run with BROWSER_CHANNEL=chrome and
PLAYWRIGHT_NODEJS_PATH=$(which node).
"""

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import httpx
import pytest

from app.core.config import Settings
from app.integrations.browser import BrowserUnavailableError, probe_browser
from app.integrations.http_probe import HttpProbe
from app.schemas.qa_config import EndpointRule, PageSpec, QaConfig
from app.schemas.runs import RunParams
from app.services.findings import IgnoreList
from app.services.quick_scan import run_quick_scan
from app.services.run_manager import RunContext
from app.services.run_store import RunStore

BUGGY_PAGE = b"""<!doctype html><html><head><title>Buggy</title></head><body>
<h1>Pricing</h1>
<img src="/missing.png" alt="hero">
<div style="width: 2000px; height: 20px; background: #eee">too wide</div>
<a href="/broken-link">Broken</a> <a href="/ok">OK</a>
<script>
  console.error('[HMR] dev server noise');
  console.error('boom: price list failed');
  fetch('/api/plans');
  fetch('/api/payments', { method: 'POST' });
</script>
</body></html>"""
OK_PAGE = (
    b"<!doctype html><html><head><title>OK</title></head><body><h1>All good</h1></body></html>"
)


class _Handler(BaseHTTPRequestHandler):
    hits: ClassVar[list[str]] = []

    def _send(self, code: int, body: bytes = b"", ctype: str = "text/html") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        _Handler.hits.append(f"GET {self.path}")
        routes = {"/": (200, BUGGY_PAGE), "/ok": (200, OK_PAGE), "/api/plans": (500, b"{}")}
        code, body = routes.get(self.path, (404, b"not found"))
        self._send(code, body)

    def do_POST(self) -> None:
        _Handler.hits.append(f"POST {self.path}")
        self._send(200, b"{}", "application/json")

    def log_message(self, format: str, *args: object) -> None:
        return  # keep test output quiet


@pytest.fixture
def site() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _Handler.hits = []
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
async def browser_settings(tmp_path: Path, site: str) -> Settings:
    settings = Settings(runs_dir=tmp_path / "runs", app_url=site)
    try:
        await probe_browser(settings.browser_channel, True)
    except BrowserUnavailableError as exc:
        pytest.skip(f"No browser available: {exc}")
    return settings


async def test_quick_scan_finds_the_planted_bugs(browser_settings: Settings) -> None:
    qa = QaConfig(
        pages=[PageSpec(path="/", name="Pricing"), PageSpec(path="/ok", name="OK")],
        risky_endpoints=[EndpointRule(url="*/api/*payment*")],
        noise_filter=[r"\[HMR\]"],
    )
    store = RunStore(browser_settings.runs_dir, 20)
    record = store.create("quick-scan", "Quick Scan", RunParams())
    ctx = RunContext(store, record, IgnoreList(browser_settings.runs_dir / "ignored.json"))

    async with httpx.AsyncClient() as client:
        await run_quick_scan(
            ctx, settings=browser_settings, qa=qa, mode="mocked", probe=HttpProbe(client)
        )
    ctx.finish()

    found = {(f.title, f.location): f.severity for f in ctx.record.findings}
    for viewport in ("desktop", "mobile"):
        assert found[("API call answered 500: GET /api/plans", f"/ · {viewport}")] == "High"
        assert found[("Broken image: /missing.png", f"/ · {viewport}")] == "Medium"
        assert found[("Broken link: /broken-link", f"/ · {viewport}")] == "Medium"
        assert found[("Console error: boom: price list failed", f"/ · {viewport}")] == "Medium"
    assert found[("Page is wider than a phone screen", "/ · mobile")] == "Medium"

    assert not [t for t, loc in found if loc.startswith("/ok")], "clean page has no findings"
    assert not [t for t, _ in found if "HMR" in t], "dev-server noise is filtered"
    assert "POST /api/payments" not in _Handler.hits, "risky endpoint never reaches the server"

    assert ctx.record.verdict == "FAILING"
    kinds = {a.kind for a in ctx.record.artifacts}
    assert kinds == {"screenshot", "trace"}
    assert all((ctx.dir / a.path).is_file() for a in ctx.record.artifacts)
    assert not (ctx.dir / ".auth-state.json").exists()
