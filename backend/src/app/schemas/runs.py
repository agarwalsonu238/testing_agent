from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Verdict = Literal["PASS", "FAILING", "BLOCKED"]
Severity = Literal["High", "Medium", "Warning"]
FailureCategory = Literal[
    "approved change", "needs approval", "regression", "automation issue", "environment"
]
RunKind = Literal["quick-scan", "check-change", "agent", "save-test", "saved-test"]
RunStatus = Literal["running", "finished"]
RunMode = Literal["mocked", "real"]
FindingStatus = Literal["open", "accepted", "ignored"]
EvidenceKind = Literal["screenshot", "design", "console", "network", "code", "log", "trace"]
StepStatus = Literal["pass", "fail", "skipped"]

AGENT_NAME_PATTERN = r"^[a-z][a-z0-9-]{1,40}$"


class Evidence(BaseModel):
    kind: EvidenceKind
    label: str
    path: str | None = None  # relative to the run folder; served by GET /runs/{id}/files/{path}
    text: str | None = None


class Finding(BaseModel):
    id: str
    agent: str  # "quick-scan", "saved-test" or an agent name
    title: str
    severity: Severity
    category: FailureCategory
    location: str  # e.g. "/pricing · mobile", "plans.py:42", "Pricing flow · step 4"
    expected: str = ""
    actual: str = ""
    suggested_fix: str | None = None
    evidence: list[Evidence] = []
    status: FindingStatus = "open"
    ignore_reason: str | None = None
    fingerprint: str = ""


class Step(BaseModel):
    index: int
    description: str
    status: StepStatus
    screenshot: str | None = None
    note: str | None = None


class Check(BaseModel):
    """A pass/fail check recorded by Playwright (never the model's own words)."""

    source: str  # e.g. "browser_wait_for", "console", "network", "pageerror"
    passed: bool
    detail: str


class AgentResult(BaseModel):
    agent: str
    task: str
    verdict: Verdict
    summary: str = ""
    blocked_reason: str | None = None
    steps: list[Step] = []
    checks: list[Check] = []
    duration_s: float | None = None
    # Relative to the run folder (e.g. "agent-output/functionality-tester-2"): where this
    # agent's evidence and recorded Playwright code live. Distinguishes repeat calls to the same
    # agent within one run (one per test case scenario) from each other.
    work_dir: str = ""


class Artifact(BaseModel):
    label: str
    path: str
    kind: EvidenceKind


class SavedTestInfo(BaseModel):
    test_id: str
    file: str
    branch: str
    commit: str | None = None
    pr_url: str | None = None
    pushed: bool = False


class RunParams(BaseModel):
    mode: RunMode = "mocked"
    agent: str | None = None
    task: str | None = None
    route: str | None = None
    flow: str | None = None
    base_ref: str | None = None
    source_run_id: str | None = None
    test_id: str | None = None


class RunRecord(BaseModel):
    """Everything stored in a run folder's `run.json`."""

    id: str
    kind: RunKind
    title: str
    status: RunStatus = "running"
    verdict: Verdict | None = None
    blocked_reason: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    params: RunParams = RunParams()
    plan_summary: str | None = None  # QA Lead's plan
    agents: list[AgentResult] = []
    findings: list[Finding] = []
    artifacts: list[Artifact] = []
    saved_test: SavedTestInfo | None = None


class RunCounts(BaseModel):
    open: int
    total: int


class RunSummary(BaseModel):
    id: str
    kind: RunKind
    title: str
    status: RunStatus
    verdict: Verdict | None
    started_at: datetime
    finished_at: datetime | None
    mode: RunMode
    counts: RunCounts


class RunDetail(RunRecord):
    counts: RunCounts
    report_summary: str  # Markdown for the PR description
    can_save_as_test: bool


class RunEvent(BaseModel):
    seq: int
    at: datetime
    level: Literal["info", "warn", "error"] = "info"
    source: str
    message: str


class RunEventsResponse(BaseModel):
    events: list[RunEvent]
    done: bool


# --- Requests ---


class QuickScanRequest(BaseModel):
    mode: RunMode = "mocked"


class CheckChangeRequest(BaseModel):
    mode: RunMode = "mocked"
    base_ref: str | None = Field(default=None, max_length=200, pattern=r"^[\w./~^@{}-]+$")
    flow: str | None = Field(default=None, max_length=4000)


class AgentRunRequest(BaseModel):
    agent: str = Field(pattern=AGENT_NAME_PATTERN)
    task: str = Field(min_length=3, max_length=4000)
    route: str | None = Field(default=None, pattern=r"^/[^\s]*$", max_length=300)
    mode: RunMode = "mocked"


class SaveTestRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    folder: Literal["isolated", "live"] | None = None


class FindingDecision(BaseModel):
    decision: Literal["accept", "ignore"]
    reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _ignore_needs_reason(self) -> "FindingDecision":
        if self.decision == "ignore" and not (self.reason and self.reason.strip()):
            raise ValueError("Ignoring a finding needs a one-line reason")
        return self


class FindingItem(Finding):
    run_id: str
    run_title: str
    run_started_at: datetime
