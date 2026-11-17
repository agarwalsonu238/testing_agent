import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.integrations.claude_code import ToolCall
from app.schemas.qa_config import ChangeRules, EndpointRule, MockSpec, QaConfig
from app.schemas.runs import Check
from app.services.agents import (
    AgentReport,
    checks_from_recording,
    checks_from_tool_calls,
    extract_playwright_code,
    flow_verdict,
    load_agents,
    parse_agent_file,
    permission_rules,
    report_to_findings,
    resolve_evidence,
    write_init_page,
    write_mcp_config,
)
from app.services.qa_config import NetworkGuard, compile_noise, route_slug
from app.services.qa_lead import classify_changes
from app.services.test_writer import next_test_id, read_registry, slugify, write_registry

QA_DIR = Path(__file__).resolve().parents[2] / "qa"


def test_shipped_agents_load_and_reviewers_cannot_write() -> None:
    agents = load_agents(QA_DIR / "agents")
    assert set(agents) == {
        "qa-lead",
        "design-reviewer",
        "functionality-tester",
        "code-reviewer",
        "test-writer",
    }
    for name in ("qa-lead", "design-reviewer", "functionality-tester", "code-reviewer"):
        allowed, disallowed = permission_rules(agents[name])
        assert not {"Write", "Edit", "Bash"} & set(allowed)
        assert {"Write", "Edit", "Bash"} <= set(disallowed)


def test_test_writer_may_only_write_in_the_test_folder() -> None:
    writer = load_agents(QA_DIR / "agents")["test-writer"]
    allowed, disallowed = permission_rules(writer, "tests/e2e/isolated/")
    assert "Write" not in allowed and "Edit" not in allowed  # no blanket write permission
    assert "Edit(tests/e2e/isolated/**)" in allowed
    assert "Bash" in disallowed
    assert "mcp__playwright__browser_run_code_unsafe" in disallowed


def test_parse_agent_file_requires_frontmatter() -> None:
    with pytest.raises(ValueError, match="frontmatter"):
        parse_agent_file("no frontmatter")
    parsed = parse_agent_file(
        "---\nname: x\ndescription: d\ntools: Read, Grep\nmcp: playwright\n---\nPrompt"
    )
    assert parsed.tools == ["Read", "Grep"]
    assert parsed.mcp == ["playwright"]
    assert parsed.prompt == "Prompt"


def _call(name: str, input_: dict[str, object], is_error: bool, text: str = "") -> ToolCall:
    return ToolCall(
        id=name,
        name=f"mcp__playwright__{name}",
        input=dict(input_),
        result_text=text,
        is_error=is_error,
    )


def test_flow_verdict_comes_from_recorded_checks() -> None:
    passed = checks_from_tool_calls([_call("browser_wait_for", {"text": "Yearly"}, False)])
    assert flow_verdict(passed) == ("PASS", None)

    retried = checks_from_tool_calls(
        [
            _call("browser_wait_for", {"text": "Yearly"}, True),
            _call("browser_wait_for", {"text": "Yearly"}, False),
        ]
    )
    assert flow_verdict(retried)[0] == "PASS"

    failed = checks_from_tool_calls([_call("browser_wait_for", {"text": "$99"}, True, "Timeout")])
    assert flow_verdict(failed)[0] == "FAILING"

    verdict, reason = flow_verdict(checks_from_tool_calls([_call("browser_click", {}, False)]))
    assert verdict == "BLOCKED" and reason


def test_recorder_log_turns_errors_into_failed_checks_and_skips_guard_blocks() -> None:
    lines = [
        json.dumps({"type": "console", "text": "[HMR] connected"}),
        json.dumps({"type": "console", "text": "TypeError: boom"}),
        json.dumps({"type": "console", "text": "TypeError: boom"}),
        json.dumps(
            {
                "type": "response",
                "status": 500,
                "method": "GET",
                "url": "http://x/api/p",
                "resourceType": "fetch",
            }
        ),
        json.dumps(
            {
                "type": "response",
                "status": 404,
                "method": "GET",
                "url": "http://x/a.png",
                "resourceType": "image",
            }
        ),
        json.dumps(
            {
                "type": "requestfailed",
                "method": "POST",
                "url": "http://x/api/pay",
                "failure": "net::ERR_BLOCKED_BY_CLIENT",
            }
        ),
        json.dumps({"type": "blocked", "method": "POST", "url": "http://x/api/pay"}),
        "not json",
    ]
    checks, blocked = checks_from_recording(lines, compile_noise([r"\[HMR\]"]))
    assert [c.detail for c in checks] == [
        "Console error: TypeError: boom",
        "GET http://x/api/p answered 500",
    ]
    assert blocked == ["POST http://x/api/pay"]
    assert (
        flow_verdict([*checks, Check(source="browser_wait_for", passed=True, detail="x")])[0]
        == "FAILING"
    )


def test_extract_playwright_code_from_tool_results() -> None:
    action = "await page.getByRole('button', { name: 'Yearly' }).click();"
    text = f"### Ran Playwright code\n```js\n{action}\n```\n### Page"
    code = extract_playwright_code(
        [_call("browser_click", {}, False, text), _call("browser_click", {}, True, text)]
    )
    assert code == [
        {
            "tool": "browser_click",
            "code": "await page.getByRole('button', { name: 'Yearly' }).click();",
        }
    ]


def test_evidence_outside_the_run_folder_is_never_served(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "agent-output").mkdir(parents=True)
    shot = run_dir / "agent-output" / "step-1.png"
    shot.write_bytes(b"png")
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"png")

    assert resolve_evidence(str(shot), run_dir).path == "agent-output/step-1.png"
    assert resolve_evidence(str(outside), run_dir).path is None
    assert resolve_evidence("../secret.png", run_dir).path is None


def test_report_findings_get_designs_and_normalized_fields(tmp_path: Path) -> None:
    run_dir = tmp_path
    (run_dir / "designs").mkdir()
    design = run_dir / "designs" / "pricing.mobile.png"
    design.write_bytes(b"png")
    report = AgentReport.model_validate(
        {
            "summary": "1 difference",
            "findings": [
                {
                    "title": "Card gap",
                    "severity": "low",
                    "category": "Regression",
                    "location": "/pricing · mobile · cards",
                    "evidence": "not a path",
                }
            ],
        }
    )
    [finding] = report_to_findings(report, "design-reviewer", run_dir, {"mobile": design})
    assert finding.severity == "Warning"
    assert finding.category == "regression"
    assert [e.kind for e in finding.evidence] == ["log", "design"]


def test_network_guard_mocks_first_then_blocks_risky() -> None:
    qa = QaConfig(
        risky_endpoints=[EndpointRule(url="*/api/*payment*")],
        mocks=[MockSpec.model_validate({"url": "*/api/plans", "method": "GET", "json": [1]})],
    )
    mocked = NetworkGuard(qa, "mocked")
    plans = mocked.decide("http://x/api/plans", "GET")
    assert plans is not None and plans.kind == "mock" and plans.body == "[1]"
    pay = mocked.decide("http://x/api/v1/payments", "POST")
    assert pay is not None and pay.kind == "block"
    assert mocked.decide("http://x/api/other", "GET") is None

    real = NetworkGuard(qa, "real")
    assert real.decide("http://x/api/plans", "GET") is None  # no mocks against the real backend
    real_pay = real.decide("http://x/api/payments", "POST")
    assert real_pay is not None and real_pay.kind == "block"


def test_init_page_and_mcp_config_are_generated(tmp_path: Path) -> None:
    guard = NetworkGuard(QaConfig(risky_endpoints=[EndpointRule(url="*/pay*")]), "real")
    init = tmp_path / "init-page.ts"
    write_init_page(QA_DIR / "init-page.template.ts", init, guard, tmp_path / "log.jsonl")
    text = init.read_text()
    assert "__RULES__" not in text and "__LOG_PATH__" not in text
    assert '"risky": [{"url": "*/pay*"' in text

    mcp = tmp_path / "mcp.json"
    write_mcp_config(
        mcp,
        settings=Settings(browser_channel="chrome", chrome_devtools_mcp=False, figma_mcp_url=None),
        servers=["playwright", "chrome-devtools", "figma"],
        output_dir=tmp_path,
        init_page=init,
        storage_state=None,
        viewport="390x844",
    )
    servers = json.loads(mcp.read_text())["mcpServers"]
    assert list(servers) == ["playwright"]  # optional servers stay off unless configured
    args = servers["playwright"]["args"]
    assert "@playwright/mcp@0.0.85" in args  # pinned
    assert args[args.index("--browser") + 1] == "chrome"
    assert args[args.index("--init-page") + 1] == str(init)


def test_classify_changes_picks_agents_by_rule() -> None:
    summary = classify_changes(
        ["app/pricing/page.tsx", "src/api/plans.py", "README.md", "tests/e2e/a.spec.ts"],
        ChangeRules(),
    )
    assert summary.ui == ["app/pricing/page.tsx"]
    assert "src/api/plans.py" in summary.logic
    assert "README.md" not in summary.files
    assert summary.agents == ["code-reviewer", "design-reviewer", "functionality-tester"]
    assert classify_changes(["docs/x.md"], ChangeRules()).agents == []


def test_next_test_id_and_registry_round_trip(tmp_path: Path) -> None:
    assert next_test_id([], "QA-", 3) == "QA-001"
    assert next_test_id(["QA-007", "QA-012", "OTHER-99", "QA-x"], "QA-", 3) == "QA-013"
    path = tmp_path / "tests" / "registry.json"
    write_registry(path, [{"id": "QA-001"}], wrapped=True)
    assert read_registry(path) == ([{"id": "QA-001"}], True)
    assert slugify("Pricing: yearly toggle!") == "pricing-yearly-toggle"
    assert route_slug("/") == "home" and route_slug("/a/b?x=1") == "a-b"
