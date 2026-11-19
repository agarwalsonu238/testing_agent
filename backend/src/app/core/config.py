import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Credentials that make Claude Code bill the API instead of the developer's subscription.
BILLED_CREDENTIAL_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


class Settings(BaseSettings):
    """Application settings, loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "QA Testing Agent API"
    environment: Literal["local", "staging", "production"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    # JSON list in env, e.g. CORS_ORIGINS=["http://localhost:4000"]
    cors_origins: list[str] = ["http://localhost:4000", "http://127.0.0.1:4000"]

    # --- App under test ---
    app_url: str = "http://localhost:3000"
    app_repo_path: Path | None = None
    designs_dir: Path = Path("./designs")

    # --- QA agent files ---
    qa_dir: Path = Path("./qa")  # qa.config.json, agents/, init-page template
    runs_dir: Path = Path("./.qa-runs")
    runs_keep: int = 20

    # --- Claude Code (headless, developer's own subscription) ---
    claude_bin: str = "claude"
    claude_code_version: str = "2.1.323"  # pinned; re-check headless auth after every upgrade
    claude_model: str | None = None  # empty = Claude Code's default for the login
    claude_run_timeout_s: int = 1200
    claude_code_oauth_token: SecretStr | None = None  # optional, from `claude setup-token`
    # Read only so the backend can refuse to start a run while they are set.
    anthropic_api_key: SecretStr | None = None
    anthropic_auth_token: SecretStr | None = None

    # --- MCP servers for agents (versions pinned) ---
    playwright_mcp_package: str = "@playwright/mcp@0.0.85"
    chrome_devtools_mcp: bool = False  # separate browser, not behind the risky-endpoint guard
    chrome_devtools_mcp_package: str = "chrome-devtools-mcp@1.13.0"
    figma_mcp_url: str | None = None  # e.g. http://127.0.0.1:3845/mcp (Figma desktop app)

    # --- Browser ---
    # "" = Playwright's own Chromium. "chrome" = installed Google Chrome (needed on macOS 12).
    browser_channel: str = ""
    browser_headless: bool = True

    # --- Real-backend mode: shared test account (never a real user's account) ---
    test_account_email: str | None = None
    test_account_password: SecretStr | None = None

    # --- Save as test ---
    test_writer_open_pr: bool = True
    diff_base: str = "origin/main"

    # --- MCP server (lets other AI coding tools - Cursor, Antigravity, etc. - call this
    # backend's own API as MCP tools; see app/mcp_server.py). Must match where the backend
    # and dashboard actually run; defaults match run-local-dev.sh. ---
    mcp_backend_url: str = "http://127.0.0.1:8400/api/v1"
    mcp_dashboard_url: str = "http://127.0.0.1:4000"

    # --- Deployed mode (optional) ---
    # Unset (default): no auth, matching the local-only design (127.0.0.1 binding is the
    # boundary). Set this once the backend is reachable from anywhere but localhost — every
    # /api/v1 request then needs a matching X-API-Key header (or ?key= for <img> tags, which
    # can't set headers).
    api_auth_token: SecretStr | None = None
    # When the app repo isn't available on disk already (a deployed backend has no local
    # checkout), clone/fetch it here on startup instead of requiring APP_REPO_PATH to pre-exist.
    # Read-only clone: never pushed to (Save as test still needs a writable local repo).
    app_repo_git_url: str | None = None  # e.g. https://github.com/org/app-repo.git
    app_repo_git_token: SecretStr | None = None  # PAT with read access, for a private repo
    app_repo_git_ref: str = "main"  # branch/tag Check my change diffs against when cloned here

    @property
    def qa_config_path(self) -> Path:
        return self.qa_dir / "qa.config.json"

    @property
    def agents_dir(self) -> Path:
        return self.qa_dir / "agents"

    @property
    def init_page_template_path(self) -> Path:
        return self.qa_dir / "init-page.template.ts"

    def billed_credentials_set(self) -> list[str]:
        """Names of API-billing credentials visible to this process (values are never returned)."""
        found: list[str] = []
        if self.anthropic_api_key and self.anthropic_api_key.get_secret_value():
            found.append("ANTHROPIC_API_KEY")
        if self.anthropic_auth_token and self.anthropic_auth_token.get_secret_value():
            found.append("ANTHROPIC_AUTH_TOKEN")
        return found


def child_process_env(settings: Settings) -> dict[str, str]:
    """Environment for subprocesses (Claude Code, git, Playwright).

    Billing credentials are always stripped, so even a key that appears after the run started
    can't make Claude Code bill the API. The optional subscription token is passed through.
    """
    env = {k: v for k, v in os.environ.items() if k not in BILLED_CREDENTIAL_VARS}
    if settings.claude_code_oauth_token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = settings.claude_code_oauth_token.get_secret_value()
    return env


@lru_cache
def get_settings() -> Settings:
    return Settings()
