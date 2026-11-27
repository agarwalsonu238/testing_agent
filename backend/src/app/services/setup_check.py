"""Setup check (plan section 5, step 7): is this machine ready to run the QA agent?"""

import asyncio

from app.core.config import Settings
from app.core.errors import PreconditionError
from app.integrations import git
from app.integrations.browser import BrowserUnavailableError, probe_browser
from app.integrations.claude_code import ClaudeCode
from app.integrations.external_reviewer import ExternalReviewer
from app.integrations.http_probe import HttpProbe
from app.integrations.process import ProcessError, run_process
from app.schemas.setup import SetupCheck, SetupItem
from app.services.agents import load_agents
from app.services.qa_config import (
    PROJECT_CONFIG,
    designs_dir,
    list_designs,
    load_qa_config,
    project_config_path,
)

SUBSCRIPTION_AUTH_METHODS = ("claude.ai", "oauth_token")


LOGIN_LABEL = "Logged in with a Claude plan"
SMOKE_LABEL = "Test run on your login"


async def _version_item(settings: Settings, claude: ClaudeCode) -> SetupItem | None:
    version = await claude.version()
    if version is None:
        return None
    pinned = settings.claude_code_version
    same = version == pinned
    return SetupItem(
        key="claude",
        label="Claude Code installed",
        status="pass" if same else "warn",
        detail=f"Version {version}" + ("" if same else f" (pinned: {pinned})"),
        fix=None
        if same
        else "Install the pinned version, or re-check headless subscription login on this "
        "version and update CLAUDE_CODE_VERSION",
    )


async def _login_item(settings: Settings, claude: ClaudeCode) -> SetupItem:
    auth = await claude.auth_status() or {}
    method = auth.get("authMethod")
    if auth.get("loggedIn") and method in SUBSCRIPTION_AUTH_METHODS:
        plan = str(auth.get("subscriptionType") or "subscription").title()
        return SetupItem(
            key="login", label=LOGIN_LABEL, status="pass", detail=f"Claude {plan} plan ({method})"
        )
    if settings.claude_code_oauth_token:
        return SetupItem(
            key="login",
            label=LOGIN_LABEL,
            status="pass",
            detail="Using CLAUDE_CODE_OAUTH_TOKEN from .env",
        )
    return SetupItem(
        key="login",
        label=LOGIN_LABEL,
        status="fail",
        detail=f"Login type: {method or 'not logged in'}",
        fix="Run `claude`, then /login with your Claude account (not an API key)",
    )


def _api_key_item(billed: list[str]) -> SetupItem:
    return SetupItem(
        key="api_key",
        label="No ANTHROPIC_API_KEY set",
        status="fail" if billed else "pass",
        detail=f"{', '.join(billed)} is set" if billed else "No API key in the environment",
        fix="Remove it from your shell profile and .env, then restart the backend"
        if billed
        else None,
    )


async def _smoke_item(claude: ClaudeCode, live: bool, billed: list[str]) -> SetupItem:
    if not live:
        return SetupItem(
            key="smoke",
            label=SMOKE_LABEL,
            status="skip",
            detail="Not run yet (uses a little plan usage)",
        )
    if billed:
        return SetupItem(
            key="smoke", label=SMOKE_LABEL, status="skip", detail="Skipped while an API key is set"
        )
    ok, detail = await claude.smoke_test()
    return SetupItem(
        key="smoke",
        label=SMOKE_LABEL,
        status="pass" if ok else "fail",
        detail=detail,
        fix=None if ok else 'Run `claude -p "hi"` in a terminal to see the error',
    )


async def _claude_items(settings: Settings, claude: ClaudeCode, live: bool) -> list[SetupItem]:
    version = await _version_item(settings, claude)
    if version is None:
        return [
            SetupItem(
                key="claude",
                label="Claude Code installed",
                status="fail",
                detail=f"`{settings.claude_bin}` was not found",
                fix="Install Claude Code, then run `claude` once and log in",
            )
        ]
    billed = settings.billed_credentials_set()
    return [
        version,
        await _login_item(settings, claude),
        _api_key_item(billed),
        await _smoke_item(claude, live, billed),
    ]


async def _browser_item(settings: Settings) -> SetupItem:
    label = "Playwright browser"
    try:
        version = await probe_browser(settings.browser_channel, True)
    except BrowserUnavailableError as exc:
        return SetupItem(
            key="browser",
            label=label,
            status="fail",
            detail=str(exc),
            fix="Run `uv run playwright install chromium` in backend/ (on macOS 12 set "
            "BROWSER_CHANNEL=chrome to use installed Google Chrome)",
        )
    channel = settings.browser_channel or "Playwright Chromium"
    return SetupItem(key="browser", label=label, status="pass", detail=f"{channel} {version}")


async def _node_item(settings: Settings) -> SetupItem:
    try:
        res = await run_process(["npx", "--version"], timeout_s=20)
        ok = res.ok
    except ProcessError:
        ok = False
    return SetupItem(
        key="node",
        label="Node.js (for Playwright MCP)",
        status="pass" if ok else "fail",
        detail=f"npx found; agents use {settings.playwright_mcp_package}"
        if ok
        else "npx not found",
        fix=None if ok else "Install Node.js 20 or newer",
    )


async def _repo_item(settings: Settings) -> SetupItem:
    repo = settings.app_repo_path
    label = "App repo (APP_REPO_PATH)"
    if repo is None:
        return SetupItem(
            key="app_repo",
            label=label,
            status="warn",
            detail="Not set",
            fix="Needed for Check my change, the Code reviewer and Save as test",
        )
    if not await git.is_repo(repo):
        return SetupItem(
            key="app_repo", label=label, status="fail", detail=f"{repo} isn't a git repository"
        )
    return SetupItem(key="app_repo", label=label, status="pass", detail=str(repo))


def _reviewer_item(settings: Settings) -> SetupItem:
    """Who reviews the test cases. The settings are already validated, so this only reports."""
    reviewer = ExternalReviewer.from_settings(settings)
    if reviewer is None:
        return SetupItem(
            key="reviewer",
            label="Test case reviewer",
            status="pass",
            detail="Claude, the same login as the other agents "
            "(set REVIEWER_PROVIDER to have Gemini, Perplexity or another AI review instead)",
        )
    return SetupItem(
        key="reviewer",
        label="Test case reviewer",
        status="pass",
        detail=f"{reviewer.label}. It is sent the draft test cases (never the diff or the "
        "flow); if it fails, Claude reviews instead",
    )


def _config_items(settings: Settings) -> list[SetupItem]:
    items = []
    try:
        qa = load_qa_config(settings)
        project = project_config_path(settings)
        source = (
            f"tool defaults + {project}"
            if project
            else f"tool defaults (add {PROJECT_CONFIG} to the project to customise)"
        )
        pages = (
            f"{len(qa.pages)} page(s) listed"
            if qa.pages
            else f"pages discovered from links (up to {qa.limits.max_pages})"
        )
        items.append(
            SetupItem(
                key="qa_config",
                label="QA config",
                status="pass",
                detail=f"{source}; {pages}; viewports: {', '.join(qa.viewports)}",
            )
        )
    except PreconditionError as exc:
        items.append(SetupItem(key="qa_config", label="QA config", status="fail", detail=str(exc)))
    try:
        agents = load_agents(settings.agents_dir)
        items.append(
            SetupItem(
                key="agents",
                label="Agent definitions",
                status="pass" if agents else "fail",
                detail=", ".join(agents) or f"none in {settings.agents_dir}",
            )
        )
    except PreconditionError as exc:
        items.append(
            SetupItem(key="agents", label="Agent definitions", status="fail", detail=str(exc))
        )
    designs = list_designs(settings)
    folder = designs_dir(settings)
    if designs or settings.figma_mcp_url:
        detail = f"{len(designs)} PNG(s) in {folder}" + (
            "; Figma MCP configured" if settings.figma_mcp_url else ""
        )
        items.append(SetupItem(key="designs", label="Designs", status="pass", detail=detail))
    else:
        items.append(
            SetupItem(
                key="designs",
                label="Designs",
                status="pass",
                detail=f"No PNGs in {folder} (optional: only the Design reviewer "
                "uses them; export <route>.desktop.png and <route>.mobile.png to enable it)",
            )
        )
    return items


async def run_setup_check(
    settings: Settings, claude: ClaudeCode, probe: HttpProbe, live: bool
) -> SetupCheck:
    """Check Claude Code, login, API key, browser, Node, app, app repo, config and designs."""
    claude_items, browser, node, app, repo = await asyncio.gather(
        _claude_items(settings, claude, live),
        _browser_item(settings),
        _node_item(settings),
        probe.reachable(settings.app_url),
        _repo_item(settings),
    )
    reachable, detail = app
    app_item = SetupItem(
        key="app",
        label=f"App reachable at {settings.app_url}",
        status="pass" if reachable else "fail",
        detail=detail,
        fix=None if reachable else "Start the app, or fix APP_URL in .env",
    )
    items = [
        *claude_items,
        browser,
        node,
        app_item,
        repo,
        _reviewer_item(settings),
        *_config_items(settings),
    ]
    return SetupCheck(ready=not any(i.status == "fail" for i in items), items=items)
