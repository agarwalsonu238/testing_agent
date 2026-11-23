from pathlib import Path

import httpx

from app.core.config import Settings
from app.integrations.claude_code import ClaudeCode
from app.integrations.http_probe import HttpProbe
from app.schemas.qa_config import QaConfig
from app.schemas.runs import RunParams
from app.services.agents import AgentDeps, LeadPlan, ReviewedCase
from app.services.findings import IgnoreList
from app.services.qa_lead import (
    _cases_for,
    design_call,
    store_test_cases,
)
from app.services.run_manager import RunContext
from app.services.run_store import RunStore


def _ctx(tmp_path: Path) -> RunContext:
    store = RunStore(tmp_path, 20)
    record = store.create("check-change", "Check my change", RunParams())
    return RunContext(store, record, IgnoreList(tmp_path / "ignored.json"))


def test_store_test_cases_maps_review_status_to_case_status_and_note(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    reviewed = [
        ReviewedCase(
            title="Normal path",
            agent="functionality-tester",
            steps=["1. Open /"],
            expected="Loads",
            review_status="approved",
        ),
        ReviewedCase(
            title="Tightened case",
            agent="api-checker",
            steps=["GET /api/v1/products"],
            expected="200",
            review_status="rewritten",
            review_note="Tightened the vague expected line",
        ),
        ReviewedCase(
            title="Unfixable case",
            agent="code-reviewer",
            steps=["check the thing"],
            expected="it works",
            review_status="rejected",
            review_note="No file:line given; can't fix without inventing one",
        ),
    ]
    store_test_cases(ctx, LeadPlan(), reviewed, "functionality-tester", [])

    by_title = {c.title: c for c in ctx.record.test_cases}
    approved = by_title["Normal path"]
    assert approved.status == "planned"
    assert approved.note is None
    assert approved.review_note is None
    assert approved.review_status == "approved"

    rewritten = by_title["Tightened case"]
    assert rewritten.status == "planned"
    assert rewritten.note is None
    assert rewritten.review_note == "Tightened the vague expected line"
    assert rewritten.review_status == "rewritten"

    rejected = by_title["Unfixable case"]
    assert rejected.status == "skipped"
    assert rejected.note == "No file:line given; can't fix without inventing one"
    assert rejected.review_note is None
    assert rejected.review_status == "rejected"


def test_store_test_cases_falls_back_to_scenarios_when_no_cases_were_reviewed(
    tmp_path: Path,
) -> None:
    ctx = _ctx(tmp_path)
    plan = LeadPlan(scenarios=["1. Do the thing.\nExpected: it works."])
    store_test_cases(ctx, plan, [], "functionality-tester", [])
    assert [c.title for c in ctx.record.test_cases] == ["1. Do the thing."]
    assert ctx.record.test_cases[0].status == "planned"


def test_cases_for_excludes_rejected_cases_and_other_agents(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    reviewed = [
        ReviewedCase(title="A", agent="code-reviewer", review_status="approved"),
        ReviewedCase(title="B", agent="code-reviewer", review_status="rejected", review_note="no"),
        ReviewedCase(title="C", agent="api-checker", review_status="approved"),
    ]
    store_test_cases(ctx, LeadPlan(), reviewed, "code-reviewer", [])
    assert [c.title for c in _cases_for(ctx, "code-reviewer")] == ["A"]
    assert [c.title for c in _cases_for(ctx, "api-checker")] == ["C"]


def test_design_call_never_grants_access_to_the_run_folder_root(tmp_path: Path) -> None:
    """The design-reviewer may read its own copied design PNG, never the run folder's root,
    where diff.patch lives."""
    run_dir = tmp_path / "run"
    designs_dir = run_dir / "designs"
    designs_dir.mkdir(parents=True)
    png = designs_dir / "pricing.desktop.png"
    png.write_bytes(b"png")
    (run_dir / "diff.patch").write_text("--- a/x\n+++ b/x\n")

    settings = Settings(designs_dir=tmp_path / "no-such-dir")
    deps = AgentDeps(
        settings=settings,
        qa=QaConfig(),
        claude=ClaudeCode(settings),
        probe=HttpProbe(httpx.AsyncClient()),
    )
    call = design_call(deps, "/pricing", "mocked", {"desktop": png})

    assert run_dir not in call.add_dirs
    assert not any((d / "diff.patch").exists() for d in call.add_dirs)
    assert any((d / png.name).is_file() for d in call.add_dirs)
