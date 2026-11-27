"""Load the QA config (the tool's generic defaults, overlaid with the tested project's own
`.qa/qa.config.json`), the design files, and the risky-endpoint / mock rules built from them."""

import json
import re
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.core.config import Settings
from app.core.errors import PreconditionError
from app.integrations.browser import RouteDecision, mock_body, url_glob_match
from app.schemas.qa_config import EndpointRule, MockSpec, QaConfig
from app.schemas.runs import RunMode

_MOCK_LIST = TypeAdapter(list[MockSpec])


# Where a tested project keeps its own QA settings and design PNGs, relative to its repo root.
PROJECT_QA_DIR = ".qa"
PROJECT_CONFIG = f"{PROJECT_QA_DIR}/qa.config.json"
PROJECT_DESIGNS = f"{PROJECT_QA_DIR}/designs"

# Safety and noise lists are added together, so a project can't drop one of the tool's rules.
_CONCAT_KEYS = ("noise_filter", "risky_endpoints", "mocks")
# Settings objects are overlaid key by key: a project sets only the fields it cares about.
_OVERLAY_KEYS = ("limits", "auth", "tests", "changes")


def project_config_path(settings: Settings) -> Path | None:
    """The tested project's `.qa/qa.config.json`, or None when there is no repo or no file."""
    if settings.app_repo_path is None:
        return None
    path = settings.app_repo_path / PROJECT_CONFIG
    return path if path.is_file() else None


def merge_qa_config(base: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
    """Overlay a project's raw config on the tool defaults (both as parsed JSON).

    Lists in `_CONCAT_KEYS` are concatenated, objects in `_OVERLAY_KEYS` are overlaid field by
    field, and every other key the project sets replaces the default.
    """
    merged = dict(base)
    for key, value in project.items():
        current = merged.get(key)
        if key in _CONCAT_KEYS and isinstance(current, list) and isinstance(value, list):
            merged[key] = current + value
        elif key in _OVERLAY_KEYS and isinstance(current, dict) and isinstance(value, dict):
            merged[key] = {**current, **value}
        else:
            merged[key] = value
    return merged


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise PreconditionError(f"{path} is not valid JSON: {exc.msg} (line {exc.lineno})") from exc
    if not isinstance(data, dict):
        raise PreconditionError(f"{path} must contain a JSON object")
    return data


def load_qa_config(settings: Settings) -> QaConfig:
    """The tool's defaults (`qa/qa.config.json`, or built-in defaults when it's missing),
    overlaid with the tested project's `.qa/qa.config.json`, plus the project's mocks file.

    Raises PreconditionError when a file exists but is invalid, naming that file.
    """
    tool_path = settings.qa_config_path
    raw = _read_json(tool_path) if tool_path.exists() else {}
    project_path = project_config_path(settings)
    if project_path is not None:
        raw = merge_qa_config(raw, _read_json(project_path))
    try:
        config = QaConfig.model_validate(raw)
    except ValidationError as exc:
        where = project_path if project_path is not None else tool_path
        raise PreconditionError(f"{where} is invalid: {exc.errors()[0]['msg']}") from exc
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


def designs_dir(settings: Settings) -> Path:
    """The tested project's `.qa/designs/` when it exists, else the tool's DESIGNS_DIR."""
    if settings.app_repo_path is not None:
        project = settings.app_repo_path / PROJECT_DESIGNS
        if project.is_dir():
            return project
    return settings.designs_dir


def list_designs(settings: Settings) -> list[str]:
    folder = designs_dir(settings)
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.glob("*.png"))


def design_files(settings: Settings, route: str) -> dict[str, Path]:
    """Design PNGs for a route by viewport, e.g. {"desktop": designs/pricing.desktop.png}."""
    slug = route_slug(route)
    folder = designs_dir(settings)
    found: dict[str, Path] = {}
    for viewport in ("desktop", "mobile"):
        path = folder / f"{slug}.{viewport}.png"
        if path.is_file():
            found[viewport] = path.resolve()
    return found
