from pathlib import Path

from app.schemas.runs import AgentResult, Finding
from app.services.findings import (
    IgnoreList,
    combine_verdicts,
    fingerprint,
    verdict_from_findings,
)


def _finding(
    title: str = "Console error", location: str = "/pricing · mobile", **kw: object
) -> Finding:
    data: dict[str, object] = {
        "id": "f1",
        "agent": "quick-scan",
        "title": title,
        "severity": "Medium",
        "category": "regression",
        "location": location,
    }
    data.update(kw)
    return Finding.model_validate(data)


def test_fingerprint_ignores_numbers_and_case() -> None:
    a = _finding(title="API call answered 500: GET /api/plans/12", location="plans.py:42")
    b = _finding(title="api call answered 503: GET /api/plans/7", location="plans.py:57")
    assert fingerprint(a) == fingerprint(b)
    assert fingerprint(a) != fingerprint(_finding(title="Broken image"))


def test_ignored_finding_is_skipped_next_time(tmp_path: Path) -> None:
    ignore = IgnoreList(tmp_path / "ignored.json")
    first = _finding()
    ignore.apply([first])
    ignore.add(first, "Known third-party widget error")

    again = _finding(id="f9")
    other = _finding(title="Broken image")
    ignore.apply([again, other])

    assert again.status == "ignored"
    assert again.ignore_reason == "Ignored before: Known third-party widget error"
    assert other.status == "open"


def test_verdict_fails_on_high_or_medium_but_not_warnings_or_ignored() -> None:
    assert verdict_from_findings([]) == "PASS"
    assert verdict_from_findings([_finding(severity="Warning")]) == "PASS"
    assert verdict_from_findings([_finding(status="ignored")]) == "PASS"
    assert verdict_from_findings([_finding(severity="High")]) == "FAILING"


def test_combined_verdict_prefers_failing_then_blocked() -> None:
    def result(verdict: str) -> AgentResult:
        return AgentResult.model_validate({"agent": "a", "task": "t", "verdict": verdict})

    assert combine_verdicts([]) is None
    assert combine_verdicts([result("PASS"), result("BLOCKED")]) == "BLOCKED"
    assert combine_verdicts([result("BLOCKED"), result("FAILING")]) == "FAILING"
    assert combine_verdicts([result("PASS")]) == "PASS"
