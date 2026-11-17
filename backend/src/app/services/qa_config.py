"""Load `qa/qa.config.json`, the design files, and the risky-endpoint /
mock rules built from them."""

import json
import re
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.core.config import Settings
from app.core.errors import PreconditionError
from app.integrations.browser import RouteDecision, mock_body, url_glob_match
from app.schemas.qa_config import EndpointRule, MockSpec, QaConfig
from app.schemas.runs import RunMode

_MOCK_LIST = TypeAdapter(list[MockSpec])


def load_qa_config(settings: Settings) -> QaConfig:
    """Read the QA config (defaults when the file is missing) and merge the app repo's mocks file.

    Raises PreconditionError when a file exists but is invalid.
    """
    path = settings.qa_config_path
    try:
        config = QaConfig.model_validate_json(path.read_text()) if path.exists() else QaConfig()
    except ValidationError as exc:
        raise PreconditionError(f"{path} is invalid: {exc.errors()[0]['msg']}") from exc
    if config.mocks_file and settings.app_repo_path:
        mocks_path = settings.app_repo_path / config.mocks_file
        if mocks_path.exists():
            try:
                config.mocks = config.mocks + _MOCK_LIST.validate_json(mocks_path.read_text())
            except ValidationError as exc:
                raise PreconditionError(
                    f"{mocks_path} is invalid: {exc.errors()[0]['msg']}"
                ) from exc
    return config


def rule_matches(rule: EndpointRule, url: str, method: str) -> bool:
    if rule.method and rule.method.upper() != method.upper():
        return False
    return url_glob_match(url, rule.url)


class NetworkGuard:
    """One risky-endpoint list for Quick Scan and agents.

    mocked mode: configured mocks answer first; risky endpoints without a mock are blocked.
    real mode: no mocks; risky endpoints are always blocked.
    """

    def __init__(self, config: QaConfig, mode: RunMode) -> None:
        self.mode = mode
        self.risky = config.risky_endpoints
        self.mocks = config.mocks if mode == "mocked" else []

    def decide(self, url: str, method: str) -> RouteDecision | None:
        for mock in self.mocks:
            if rule_matches(mock, url, method):
                body, headers = mock_body(mock.json_body, mock.body)
                return RouteDecision(
                    kind="mock",
                    label=f"mock {mock.url}",
                    status=mock.status,
                    body=body,
                    headers={**headers, **mock.headers},
                )
        for rule in self.risky:
            if rule_matches(rule, url, method):
                return RouteDecision(kind="block", label=f"risky endpoint {rule.url}")
        return None

    def as_json(self) -> str:
        """Rules for the agents' Playwright init-page (same semantics as `decide`)."""
        mocks = [
            {
                "url": m.url,
                "method": m.method,
                "status": m.status,
                "body": mock_body(m.json_body, m.body)[0],
                "headers": {**mock_body(m.json_body, m.body)[1], **m.headers},
            }
            for m in self.mocks
        ]
        risky = [{"url": r.url, "method": r.method} for r in self.risky]
        return json.dumps({"mocks": mocks, "risky": risky})


def compile_noise(patterns: list[str]) -> list[re.Pattern[str]]:
    compiled = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except re.error as exc:
            raise PreconditionError(f"Bad noise_filter regex {pattern!r}: {exc}") from exc
    return compiled


def route_slug(route: str) -> str:
    """`/` → `home`, `/pricing` → `pricing`, `/a/b` → `a-b` (design file naming)."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", route.split("?")[0].strip("/")).strip("-").lower()
    return slug or "home"


def list_designs(settings: Settings) -> list[str]:
    if not settings.designs_dir.is_dir():
        return []
    return sorted(p.name for p in settings.designs_dir.glob("*.png"))


def design_files(settings: Settings, route: str) -> dict[str, Path]:
    """Design PNGs for a route by viewport, e.g. {"desktop": designs/pricing.desktop.png}."""
    slug = route_slug(route)
    found: dict[str, Path] = {}
    for viewport in ("desktop", "mobile"):
        path = settings.designs_dir / f"{slug}.{viewport}.png"
        if path.is_file():
            found[viewport] = path.resolve()
    return found
