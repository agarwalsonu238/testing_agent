"""Shape of `qa/qa.config.json`: the one config file next to `.env` (page list,
limits, noise filter,
risky endpoints, mocks, login, test folders)."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class PageSpec(BaseModel):
    path: str = Field(pattern=r"^/")
    name: str


class Viewport(BaseModel):
    width: int = Field(ge=200)
    height: int = Field(ge=200)
    is_mobile: bool = False


class Limits(BaseModel):
    slow_api_ms: int = 2000
    slow_page_ms: int = 5000
    page_timeout_ms: int = 30000
    max_links_per_page: int = 25


class EndpointRule(BaseModel):
    """A URL glob (`*` matches anything, including `/`) with an optional HTTP method."""

    url: str
    method: str | None = None


class MockSpec(EndpointRule):
    status: int = 200
    json_body: Any = Field(default=None, alias="json")
    body: str | None = None
    headers: dict[str, str] = {}


class LoginForm(BaseModel):
    path: str = Field(pattern=r"^/")
    email_selector: str
    password_selector: str
    submit_selector: str
    success_url: str  # glob the URL must match after submit


class AuthConfig(BaseModel):
    # Playwright storage-state file (relative to the app repo) used as the mock login.
    mock_storage_state: str | None = None
    # Real-backend mode logs in with the shared test account (TEST_ACCOUNT_* in .env).
    login: LoginForm | None = None


class TestsConfig(BaseModel):
    isolated_dir: str = "tests/e2e/isolated"
    live_dir: str = "tests/e2e/live"
    default_folder: Literal["isolated", "live"] = "isolated"
    registry_path: str = "tests/registry.json"
    id_prefix: str = "QA-"
    id_digits: int = Field(default=3, ge=1, le=8)
    playwright_cwd: str = "."
    playwright_command: list[str] = ["npx", "playwright", "test"]
    pr_base: str = "main"
    branch_prefix: str = "qa/save-test-"


class ChangeRules(BaseModel):
    """How the QA Lead classifies changed files (globs, matched against repo-relative paths)."""

    ui: list[str] = [
        "*.tsx",
        "*.jsx",
        "*.css",
        "*.scss",
        "*.html",
        "*.svg",
        "*/components/*",
        "*/styles/*",
    ]
    logic: list[str] = ["*.ts", "*.js", "*.py", "*/api/*", "*/hooks/*", "*/lib/*", "*/services/*"]
    ignore: list[str] = [
        "*.md",
        "*.lock",
        "*package-lock.json",
        "*/tests/*",
        "*.test.*",
        "*.spec.*",
    ]


class QaConfig(BaseModel):
    pages: list[PageSpec] = [PageSpec(path="/", name="Home")]
    viewports: dict[str, Viewport] = {
        "desktop": Viewport(width=1440, height=900),
        "mobile": Viewport(width=390, height=844, is_mobile=True),
    }
    limits: Limits = Limits()
    noise_filter: list[str] = []  # regexes; matching console lines / request URLs are dropped
    api_url_pattern: str = "*/api/*"
    risky_endpoints: list[EndpointRule] = []
    mocks: list[MockSpec] = []
    mocks_file: str | None = (
        None  # JSON list of MockSpec in the app repo (the isolated tests' mocks)
    )
    auth: AuthConfig = AuthConfig()
    tests: TestsConfig = TestsConfig()
    changes: ChangeRules = ChangeRules()
